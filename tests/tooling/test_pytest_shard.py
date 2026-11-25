"""One shard of a marker band runs its slice and no one else's."""

import re
from functools import partial
from pathlib import Path

import pytest
import yaml

from tests.tooling.script_support import load

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "shard.py"


load_script = partial(load, SCRIPT)


class TestShardIds:
    """Round-robin covers everything exactly once."""

    @pytest.mark.medium
    def test_four_shards_partition(self, tmp_path, monkeypatch) -> None:
        shard = load_script()
        (tmp_path / "test_collection.py").write_text(
            "import warnings\n"
            "import pytest\n"
            'warnings.warn("Test: test_collection.py::test_phantom", '
            "DeprecationWarning)\n"
            '@pytest.mark.parametrize("value", range(10))\n'
            "def test_real(value): pass\n"
        )
        monkeypatch.setattr(shard, "ROOT", tmp_path)
        monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))
        ids = shard.collect_ids("")
        assert ids == [f"test_collection.py::test_real[{i}]" for i in range(10)]
        assert shard.collect_ids("missing") == []
        (tmp_path / "test_broken.py").write_text('raise ValueError("bad collection")')
        with pytest.raises(RuntimeError, match="bad collection"):
            shard.collect_ids("")
        parts = [shard.shard_ids(ids, i, 4) for i in range(4)]
        assert sorted(n for part in parts for n in part) == ids
        assert len({n for part in parts for n in part}) == len(ids)

    def test_more_shards_than_tests_leaves_empties(self) -> None:
        shard = load_script()
        ids = ["tests/t.py::test_0"]
        assert shard.shard_ids(ids, 0, 4) == ids
        assert shard.shard_ids(ids, 3, 4) == []

    def test_out_of_range_shard_is_rejected(self) -> None:
        shard = load_script()
        with pytest.raises(SystemExit):
            shard.shard_main(["--marker", "slow", "--shard", "4", "--shards", "4"])

    def test_an_empty_slice_exits_clean_without_running_pytest(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fewer tests than shards is not a failure in any of them."""
        shard = load_script()
        monkeypatch.setattr(shard, "collect_ids", lambda _marker: [])
        assert (
            shard.shard_main(["--marker", "slow", "--shard", "3", "--shards", "4"]) == 0
        )


@pytest.mark.medium
def test_timed_out_collection_keeps_partial_log(tmp_path, monkeypatch, capsys):
    shard = load_script()
    monkeypatch.setattr(shard, "ROOT", tmp_path)
    monkeypatch.setattr(shard, "_COLLECTION_TIMEOUT", 2.0)
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))
    (tmp_path / "test_blocked.py").write_text(
        "from time import sleep\n"
        "print('started importing test_blocked')\n"
        "sleep(20)\n"
        "print('finished importing test_blocked')\n",
        encoding="utf-8",
    )
    assert shard.shard_main(["--marker", "", "--shard", "0", "--shards", "1"]) == 2
    message = capsys.readouterr().err
    assert "collection for -m '' timed out after 2s" in message
    log = Path(message.partition("[log] ")[2].strip())
    contents = log.read_text(encoding="utf-8")
    assert "started importing test_blocked" in contents
    assert "finished importing test_blocked" not in contents


@pytest.mark.medium
def test_invalid_marker_reports_the_error_and_keeps_the_collection_log(
    tmp_path, monkeypatch, capsys
) -> None:
    shard = load_script()
    monkeypatch.setattr(shard, "ROOT", tmp_path)
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))
    (tmp_path / "test_collection.py").write_text(
        "def test_probe():\n    pass\n", encoding="utf-8"
    )
    assert shard.shard_main(["--marker", "not (", "--shard", "0", "--shards", "1"]) == 2
    message = capsys.readouterr().err
    assert "Wrong expression passed to '-m'" in message
    assert "Traceback" not in message
    assert "test_collection.py::test_probe" not in message
    log = Path(message.partition("[log] ")[2].strip())
    assert log.parent == tmp_path / "notes/verification"
    contents = log.read_text(encoding="utf-8")
    assert "test_collection.py::test_probe" in contents
    assert "Wrong expression passed to '-m'" in contents


@pytest.mark.parametrize("output", ["manifest", "coverage", "coverage receipt"])
def test_shard_refuses_to_overwrite_timings_before_collection(
    tmp_path, monkeypatch, capsys, output
):
    shard = load_script()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(shard, "collect_ids", lambda _: pytest.fail("collected tests"))
    coverage = tmp_path / ".coverage"
    timing = (
        tmp_path / "timings.json"
        if output == "manifest"
        else coverage
        if output == "coverage"
        else shard.coverage_evidence.sidecar(coverage)
    )
    original = b'{"test_probe.py::test_probe":1}\n'
    timing.write_bytes(original)
    options = (
        ["--manifest", str(timing)]
        if output == "manifest"
        else ["--bind-coverage", str(coverage), "--", "--cov-branch"]
    )
    assert (
        shard.shard_main(
            [
                "--marker",
                "",
                "--shard",
                "0",
                "--shards",
                "1",
                "--durations",
                timing.name,
                *options,
            ]
        )
        == 2
    )
    diagnostic = capsys.readouterr().err
    assert "would replace --durations" in diagnostic
    assert str(timing) in diagnostic
    assert timing.read_bytes() == original


def test_stale_exclusions_name_the_nodes_without_replacing_the_manifest(
    tmp_path, monkeypatch, capsys
) -> None:
    shard = load_script()
    manifest = tmp_path / "shard.json"
    manifest.write_bytes(b"previous\n")
    existing = "tests/test_sample.py::test_ok"
    missing = ["tests/test_sample.py::test_old", "tests/test_sample.py::test_typo"]
    monkeypatch.setattr(shard, "collect_ids", lambda _: [existing])
    monkeypatch.setattr(
        shard.subprocess, "run", lambda *_args, **_kwargs: pytest.fail("ran pytest")
    )
    status = shard.shard_main(
        [
            "--marker",
            "",
            "--shard",
            "0",
            "--shards",
            "1",
            "--manifest",
            str(manifest),
            *(f"--exclude-node={node}" for node in [existing, *missing]),
        ]
    )
    assert status == 2
    message = capsys.readouterr().err
    assert message.startswith("--exclude-node: not in the collected corpus:")
    assert all(node in message for node in missing)
    assert existing not in message
    assert "Traceback" not in message
    assert manifest.read_bytes() == b"previous\n"


def test_duration_assignment_improves_longest_shard_and_covers_unknowns() -> None:
    shard = load_script()
    ids = list("abcdefghij")
    durations = dict(zip(ids, [10, 9, 8, 7, 1, 1, 1, 1, 1, 1], strict=True))
    parts = [shard.shard_ids(ids, i, 3, durations) for i in range(3)]
    assert sorted(node for part in parts for node in part) == ids
    before = max(sum(durations[n] for n in ids[i::3]) for i in range(3))
    after = max(sum(durations[n] for n in part) for part in parts)
    assert after < before
    assert shard.shard_ids(list(reversed(ids)), 0, 3, durations) == parts[0]
    assert (
        sorted(n for i in range(3) for n in shard.shard_ids(ids, i, 3, {"a": 10}))
        == ids
    )
    assert shard.shard_ids(ids, 0, 3, {"stale": 5})


@pytest.mark.parametrize(
    "payload", ["[]", '{"a": -1}', '{"a": true}', '{"a": NaN}', '{"a": 1e-400}']
)
def test_bad_durations_are_refused(tmp_path, payload) -> None:
    path = tmp_path / "durations.json"
    path.write_text(payload)
    with pytest.raises(ValueError, match="finite positive"):
        load_script().load_durations(path)


def test_shard_reports_an_overflowing_duration_before_collection(
    tmp_path, monkeypatch, capsys
):
    shard = load_script()
    path = tmp_path / "timings.json"
    path.write_text(f'{{"test_example": {10**400}}}')
    monkeypatch.setattr(shard, "collect_ids", lambda _: pytest.fail("collected tests"))
    assert (
        shard.shard_main(
            [
                "--marker",
                "slow",
                "--shard",
                "0",
                "--shards",
                "1",
                "--durations",
                str(path),
            ]
        )
        == 2
    )
    message = capsys.readouterr().err
    assert str(path) in message
    assert "duration for 'test_example' must be finite positive seconds" in message


def test_invalid_shard_arguments_are_refused() -> None:
    with pytest.raises(ValueError, match="invalid shard"):
        load_script().shard_ids([], -1, 2)


@pytest.mark.parametrize("option", ["--duraton", "--durat", "-n"])
def test_only_pytest_options_after_the_separator_are_forwarded(
    monkeypatch, capsys, option
) -> None:
    shard = load_script()
    monkeypatch.setattr(shard, "collect_ids", lambda _: pytest.fail("collected tests"))
    base = ["--marker", "", "--shard", "0", "--shards", "1"]
    with pytest.raises(SystemExit) as caught:
        shard.shard_main([*base, option, "0", "--", "-n", "0"])
    assert caught.value.code == 2
    assert f"unrecognized arguments: {option} 0" in capsys.readouterr().err
    selected, forwarded = shard._parse_args([*base, "--", "-n", "0", "--shard", "9"])
    assert selected.shard == 0
    assert forwarded == ["-n", "0", "--shard", "9"]


@pytest.mark.parametrize(
    ("excluded", "expected"),
    [
        ([], "18.0s (1 tests use median fallback 6.000s)"),
        (["a"], "4.0s (1 tests use median fallback 2.000s)"),
        (["a", "b"], "1.0s (1 tests use median fallback 1.000s)"),
    ],
)
def test_shard_reports_estimate_and_unknown_weights(
    tmp_path, monkeypatch, capsys, excluded, expected
) -> None:
    shard = load_script()
    path = tmp_path / "durations.json"
    path.write_text('{"a": 10, "b": 2, "stale": 1000}')
    monkeypatch.setattr(shard, "collect_ids", lambda _marker: ["a", "b", "c"])
    monkeypatch.setattr(
        shard.subprocess,
        "run",
        lambda *_args, **_kwargs: type("Result", (), {"returncode": 0})(),
    )
    assert (
        shard.shard_main(
            [
                "--marker",
                "slow",
                "--shard",
                "0",
                "--shards",
                "1",
                "--durations",
                str(path),
                *(f"--exclude-node={node}" for node in excluded),
            ]
        )
        == 0
    )
    assert expected in capsys.readouterr().out


def test_progress_survives_without_publishing_complete_evidence(tmp_path) -> None:
    import json
    from types import SimpleNamespace

    shard = load_script()
    destination = tmp_path / "durations.json"
    recorder = shard.Recorder(destination)
    recorder.pytest_runtest_logreport(
        SimpleNamespace(
            nodeid="a",
            when="call",
            duration=2,
            failed=True,
            longrepr="broken invariant",
        )
    )
    recorder.pytest_runtest_logreport(
        SimpleNamespace(nodeid="a", when="teardown", duration=0.5, failed=False)
    )
    entries = [json.loads(line) for line in recorder.progress.read_text().splitlines()]
    assert entries[0]["failure"] == "broken invariant"
    assert entries[0]["finished"] is False
    assert entries[1] == {
        "nodeid": "a",
        "duration": 2.5,
        "finished": True,
        "failed": True,
    }
    assert not destination.exists()
    assert not destination.with_suffix(".json.meta.json").exists()
    recorder.pytest_sessionfinish(1)
    assert json.loads(destination.read_text()) == {"a": 2.5}
    assert (
        json.loads(destination.with_suffix(".json.meta.json").read_text())["exitstatus"]
        == 1
    )


@pytest.mark.parametrize("workflow", ["ci", "weekly"])
def test_workflow_timing_evidence_stays_in_scratch_and_is_uploaded(workflow) -> None:
    document = yaml.safe_load(
        (REPO_ROOT / ".github/workflows" / f"{workflow}.yml").read_text()
    )
    found = 0
    for job in document["jobs"].values():
        steps = job.get("steps", [])
        uploads = [
            pattern
            for step in steps
            if step.get("uses", "").startswith("actions/upload-artifact@")
            for pattern in step["with"]["path"].splitlines()
        ]
        for step in steps:
            for filename in re.findall(
                r"--duration-output\s+(\S+)", step.get("run", "")
            ):
                path = Path(filename)
                assert path.is_relative_to("notes/ci"), filename
                for emitted in (path, Path(filename + ".progress.jsonl")):
                    assert any(emitted.match(pattern) for pattern in uploads), emitted
                found += 1
            for filename in re.findall(r"--manifest\s+(\S+)", step.get("run", "")):
                assert Path(filename).is_relative_to("notes/ci"), filename
                assert any(Path(filename).match(pattern) for pattern in uploads), (
                    filename
                )
    assert found
