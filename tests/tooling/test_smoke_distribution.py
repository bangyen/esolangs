"""Distribution batches retain all rows and a bounded isolated process."""

import io
import os
import stat
import subprocess
import sys
import tarfile
import traceback
from pathlib import Path

import pytest

import esolangs
from scripts.ci import release as smoke


def test_cli_smoke_failure_exposes_the_child_diagnostic() -> None:
    with pytest.raises(subprocess.CalledProcessError) as caught:
        smoke._cli(["list", "--smoke-probe-unknown-option"])
    assert caught.value.returncode == 2
    displayed = "".join(traceback.format_exception_only(caught.value))
    assert "returned non-zero exit status 2" in displayed
    assert "unknown option: --smoke-probe-unknown-option" in displayed


def test_generator_batch_executes_all_rows() -> None:
    smoke._generator_process("Brainfuck", image_extra=True)


@pytest.mark.medium
def test_saved_template_smoke_runs_all_rows_through_the_cli(tmp_path) -> None:
    smoke._smoke_saved_template(tmp_path)


def test_generator_batch_rejects_a_wrong_table(monkeypatch) -> None:
    monkeypatch.setattr(smoke, "_evaluator", lambda: lambda *_args, **_kwargs: "0000")
    with pytest.raises(AssertionError, match="Brainfuck"):
        smoke._generator("Brainfuck", image_extra=False)


def test_a_missing_dependency_fails_the_generator_smoke(monkeypatch) -> None:
    # No language needs an extra to run, so a refusal is a packaging fault.
    def missing(*_args, **_kwargs):
        raise esolangs.MissingDependencyError("extra missing")

    monkeypatch.setattr(smoke, "_evaluator", lambda: missing)
    with pytest.raises(esolangs.MissingDependencyError):
        smoke._generator("Brainfuck", image_extra=False)


@pytest.mark.parametrize("extra", [False, True])
def test_generator_process_keeps_the_deadline_and_propagates_failure(
    monkeypatch, extra
) -> None:
    def run(args, **kwargs):
        assert "-I" in args
        assert args[args.index("--language") + 1] == "Brainfuck"
        assert ("--image" in args) == extra
        assert kwargs == {"timeout": 30, "check": True}
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(smoke.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        smoke._generator_process("Brainfuck", image_extra=extra)


def test_the_generator_self_invocation_is_accepted_by_the_dispatcher(
    monkeypatch,
) -> None:
    """The batch child must name the ``smoke`` subcommand.

    ``main`` dispatches on the first argument, so a bare ``--language`` reads
    as an unknown subcommand and the whole distribution smoke test fails.
    """
    captured: dict[str, list[str]] = {}

    def run(args, **_kwargs):
        captured["args"] = list(args)
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(smoke.subprocess, "run", run)
    monkeypatch.setattr(smoke, "_generator", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sys, "argv", ["release.py"])
    with pytest.raises(subprocess.CalledProcessError):
        smoke._generator_process("Brainfuck", image_extra=False)
    assert smoke.main(captured["args"][3:]) == 0


def test_image_only_pass_runs_every_raster_and_skips_text(monkeypatch) -> None:
    runs = []
    monkeypatch.setattr(
        smoke,
        "_generator_process",
        lambda name, *, image_extra: runs.append((name, image_extra)),
    )

    def full_check(*_args):
        pytest.fail("image-only pass ran a full wheel check")

    monkeypatch.setattr(smoke, "_smoke_install", full_check)
    monkeypatch.setattr(smoke, "_smoke_files", full_check)
    monkeypatch.setattr(smoke, "_smoke_deadlines", full_check)
    assert smoke.main(["smoke", "--image-only"]) == 0
    rasters = [
        name
        for name in esolangs.list_languages()
        if (facts := esolangs.describe(name)).boolean_generator
        and facts.source_kind == "raster"
    ]
    assert rasters
    assert runs == [(name, True) for name in rasters]


def test_normalize_help_and_missing_paths_are_checked_before_the_epoch(
    monkeypatch, capsys
) -> None:
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    with pytest.raises(SystemExit) as help_exit:
        smoke.main(["normalize", "--help"])
    assert help_exit.value.code == 0
    assert "archives" in capsys.readouterr().out
    with pytest.raises(SystemExit) as missing_paths:
        smoke.main(["normalize"])
    assert missing_paths.value.code == 2
    assert "the following arguments are required: archives" in capsys.readouterr().err


@pytest.mark.parametrize("epoch", [None, "not seconds", "-1", str(2**32)])
def test_normalize_rejects_invalid_epoch_before_opening_archives(
    monkeypatch, capsys, epoch
) -> None:
    if epoch is None:
        monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    else:
        monkeypatch.setenv("SOURCE_DATE_EPOCH", epoch)
    monkeypatch.setattr(
        smoke,
        "_staged_normalization",
        lambda *_, **_kwargs: pytest.fail("opened archive"),
    )
    with pytest.raises(SystemExit) as caught:
        smoke.main(["normalize", "first.tar.gz", "second.tar.gz"])
    assert caught.value.code == 2
    assert "SOURCE_DATE_EPOCH must be an integer" in capsys.readouterr().err


@pytest.mark.parametrize("failure", ["stage", "publish"])
def test_normalize_preserves_archives_when_a_batch_fails(
    tmp_path, monkeypatch, capsys, failure
) -> None:
    first, second = (tmp_path / name for name in ("first.tar.gz", "second.tar.gz"))
    for path in (first, second):
        with tarfile.open(path, "w:gz") as output:
            output.addfile(tarfile.TarInfo("example"))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    if failure == "stage":
        second.write_bytes(b"corrupt archive")
    original = first.read_bytes(), second.read_bytes()
    replace = Path.replace

    def fail_publication(path, target):
        if path.name == "normalized" and target == second.resolve():
            raise OSError("injected publication failure")
        return replace(path, target)

    with monkeypatch.context() as patch:
        if failure == "publish":
            patch.setattr(Path, "replace", fail_publication)
        with pytest.raises(SystemExit) as caught:
            smoke.main(["normalize", str(first), str(second)])
    assert caught.value.code == 1
    assert str(second) in capsys.readouterr().err
    assert (first.read_bytes(), second.read_bytes()) == original
    assert set(tmp_path.iterdir()) == {first, second}

    if failure == "stage":
        second.write_bytes(original[0])
    assert smoke.main(["normalize", str(first), str(second)]) == 0
    for path in (first, second):
        with tarfile.open(path) as archive:
            assert archive.getmember("example").mtime == 1700000000


def test_failed_release_restore_preserves_the_original_for_recovery(
    tmp_path, monkeypatch, capsys
) -> None:
    targets = [tmp_path / f"{index}.tar.gz" for index in range(3)]
    for path in targets:
        with tarfile.open(path, "w:gz") as archive:
            archive.addfile(tarfile.TarInfo("example"))
    originals = [path.read_bytes() for path in targets]
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    replace = Path.replace

    def replace_with_failures(path, target):
        if path.name == "normalized" and target == targets[2].resolve():
            raise OSError("injected publication failure")
        if path.name == "original" and target == targets[1].resolve():
            raise OSError("injected restore failure")
        return replace(path, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", replace_with_failures)
        with pytest.raises(SystemExit) as caught:
            smoke.main(["normalize", *(str(path) for path in targets)])
    assert caught.value.code == 1
    message = capsys.readouterr().err
    assert f"{targets[2]}: injected publication failure" in message
    assert (
        f"could not restore {targets[1].resolve()}: injected restore failure" in message
    )
    backup = Path(message.partition("original archive kept at ")[2].strip())
    assert backup.read_bytes() == originals[1]
    assert set(tmp_path.iterdir()) == {*targets, backup.parent}
    backup.replace(targets[1])
    assert [path.read_bytes() for path in targets] == originals


def test_normalize_without_an_installed_package(tmp_path) -> None:
    archive = tmp_path / "source.tar.gz"
    payload = b"source payload\n"
    member = tarfile.TarInfo("package/source.py")
    member.size = len(payload)
    member.mtime = 123456
    member.uid, member.gid = 42, 43
    member.uname, member.gname = "builder", "builders"
    member.pax_headers = {"mtime": "123456.5", "atime": "123457", "ctime": "123458"}
    with tarfile.open(archive, "w:gz", format=tarfile.PAX_FORMAT) as source:
        source.addfile(member, io.BytesIO(payload))
    archive.chmod(0o640)
    mode = stat.S_IMODE(archive.stat().st_mode)
    script = Path(smoke.__file__).resolve()
    # -I -S excludes both the checkout and installed site packages.
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(script), "normalize", str(archive)],
        env={**os.environ, "SOURCE_DATE_EPOCH": "1700000000"},
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert stat.S_IMODE(archive.stat().st_mode) == mode
    assert int.from_bytes(archive.read_bytes()[4:8], "little") == 1700000000
    with tarfile.open(archive) as source:
        normalized = source.getmember(member.name)
        assert normalized.mtime == 1700000000
        assert (normalized.uid, normalized.gid) == (0, 0)
        assert (normalized.uname, normalized.gname) == ("", "")
        assert not {"mtime", "atime", "ctime"} & normalized.pax_headers.keys()
        stream = source.extractfile(normalized)
        assert stream is not None
        assert stream.read() == payload


def test_normalize_leaves_original_if_compression_fails(tmp_path, monkeypatch) -> None:
    archive = tmp_path / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as source:
        member = tarfile.TarInfo("package/source.py")
        member.size = 1
        source.addfile(member, io.BytesIO(b"x"))
    original = archive.read_bytes()

    def fail(*_args):
        raise OSError("compression write failed")

    monkeypatch.setattr(smoke.gzip.GzipFile, "write", fail)
    with pytest.raises(OSError, match="compression write failed"):
        smoke.normalize(archive, 0)
    assert archive.read_bytes() == original
    assert list(tmp_path.iterdir()) == [archive]


def test_normalize_discards_global_and_local_pax_ownership(tmp_path) -> None:
    payload = b"source payload\n"
    ids = {"uid", "gid", "uname", "gname"}
    shared = {"comment": "preserve unrelated PAX metadata"}
    archives = []
    for index in (1, 2):
        ownership = {
            "uid": str(index * 100_000),
            "gid": str(index * 200_000),
            "uname": f"builder-{index}",
            "gname": f"group-{index}",
        }
        archive = tmp_path / f"source-{index}.tar.gz"
        archives.append(archive)
        member = tarfile.TarInfo("package/source.py")
        member.size = len(payload)
        member.pax_headers = shared | (ownership if index == 1 else {})
        with tarfile.open(
            archive,
            "w:gz",
            format=tarfile.PAX_FORMAT,
            pax_headers=ownership if index == 2 else {},
        ) as source:
            source.addfile(member, io.BytesIO(payload))
        with tarfile.open(archive) as source:
            assert ids <= source.getmember(member.name).pax_headers.keys()

    assert archives[0].read_bytes() != archives[1].read_bytes()
    for archive in archives:
        smoke.normalize(archive, 1700000000)
    assert archives[0].read_bytes() == archives[1].read_bytes()
    with tarfile.open(archives[0]) as source:
        normalized = source.getmember("package/source.py")
        assert (normalized.uid, normalized.gid) == (0, 0)
        assert (normalized.uname, normalized.gname) == ("", "")
        assert normalized.pax_headers == shared
        stream = source.extractfile(normalized)
        assert stream is not None
        assert stream.read() == payload


def test_normalize_streams_members_in_archive_order(tmp_path, monkeypatch) -> None:
    archive = tmp_path / "source.tar.gz"
    members = {"package/z": b"x" * (64 * 1024), "package/a": b"last"}
    with tarfile.open(archive, "w:gz") as source:
        for name, payload in members.items():
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            source.addfile(member, io.BytesIO(payload))
    with monkeypatch.context() as patch:
        patch.setattr(
            tarfile.TarFile,
            "getmembers",
            lambda _: pytest.fail("read every header first"),
        )
        smoke.normalize(archive, 1700000000)
    normalized = archive.read_bytes()
    smoke.normalize(archive, 1700000000)
    assert archive.read_bytes() == normalized
    with tarfile.open(archive) as source:
        assert source.getnames() == list(members)
        for member in source:
            content = source.extractfile(member)
            assert content is not None
            assert content.read() == members[member.name]


def test_release_notes_are_the_tag_changelog_section() -> None:
    changelog = "# Changelog\n\n## 1.1.0\n\n- New.\n\n## 1.0.0\n\n- Old.\n"
    assert smoke.notes("v1.1.0", changelog) == "- New.\n"
    assert smoke.notes("1.0.0", changelog) == "- Old.\n"
    with pytest.raises(SystemExit, match=r"no '## 1\.2\.0' section"):
        smoke.notes("v1.2.0", changelog)
    with pytest.raises(SystemExit, match="empty"):
        smoke.notes("v1.1.0", "## 1.1.0\n\n## 1.0.0\n- Old.\n")


def test_every_source_path_checks_out_on_windows() -> None:
    """``what!?.txt`` failed every Windows checkout; macOS and Linux accept it."""
    src = Path(__file__).parents[2] / "src"
    refused = sorted(
        str(path.relative_to(src))
        for path in src.rglob("*")
        if set(path.name) & set('<>:"\\|?*') or path.name.endswith((" ", "."))
    )
    assert not refused, refused
