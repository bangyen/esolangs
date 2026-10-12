"""Distribution batches retain all rows and a bounded isolated process."""

import io
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

import esolangs
from scripts.ci import release as smoke


def test_generator_batch_executes_all_rows() -> None:
    smoke._generator("Brainfuck", math_extra=False, image_extra=True)  # noqa: SLF001


def test_generator_batch_rejects_a_wrong_table(monkeypatch) -> None:
    monkeypatch.setattr(
        "esolangs.runtime._evaluate._evaluate", lambda *_args, **_kwargs: "0000"
    )
    with pytest.raises(AssertionError, match="Brainfuck"):
        smoke._generator("Brainfuck", math_extra=False, image_extra=False)  # noqa: SLF001


@pytest.mark.parametrize("math_extra", [False, True])
def test_missing_math_is_only_allowed_without_the_extra(
    monkeypatch, math_extra
) -> None:
    def missing(*_args, **_kwargs):
        raise esolangs.MissingDependencyError("math extra missing")

    monkeypatch.setattr("esolangs.runtime._evaluate._evaluate", missing)
    if math_extra:
        with pytest.raises(AssertionError):
            smoke._generator("Brainfuck", math_extra=True, image_extra=False)  # noqa: SLF001
    else:
        smoke._generator("Brainfuck", math_extra=False, image_extra=False)  # noqa: SLF001


@pytest.mark.parametrize("extra", [False, True])
def test_generator_process_keeps_the_deadline_and_propagates_failure(
    monkeypatch, extra
) -> None:
    def run(args, **kwargs):
        assert "-I" in args
        assert args[args.index("--language") + 1] == "Brainfuck"
        assert ("--math" in args) == extra
        assert ("--image" in args) == extra
        assert kwargs == {"timeout": 30, "check": True}
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(smoke.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        smoke._generator_process("Brainfuck", math_extra=extra, image_extra=extra)  # noqa: SLF001


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
        smoke._generator_process("Brainfuck", math_extra=False, image_extra=False)  # noqa: SLF001
    assert smoke.main(captured["args"][3:]) == 0


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
