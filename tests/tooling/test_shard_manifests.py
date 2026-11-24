"""Shard evidence proves successful, exactly-once execution of fresh collection."""

import json
import subprocess
import sys
from pathlib import Path
from shutil import copytree

import pytest

from checks.check_shard_manifests import check
from scripts.ci.shard import Recorder, load_durations, load_run, refresh, refresh_main


def evidence(tmp_path):
    paths = []
    for index, selected in enumerate((["a"], ["b"])):
        directory = tmp_path / str(index)
        directory.mkdir()
        path = directory / "tests.shard.json"
        recorder = Recorder(directory / "test-durations.json")
        recorder.collected.update(selected + (["serial"] if index == 0 else []))
        recorder.finished.update(recorder.collected)
        recorder.durations.update(dict.fromkeys(recorder.collected, 1))
        recorder.pytest_sessionfinish(0)
        # Mirror pytest_shard: the manifest carries the same run identity the
        # Recorder stamps from GITHUB_* (and platform) into its sidecar.  A
        # null identity here would disagree with the sidecar in CI, where
        # those variables are set, and check() would fail closed on the
        # identity before ever reaching the injected fault.
        run = json.loads((directory / "test-durations.json.meta.json").read_text())[
            "run"
        ]
        path.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "shard": index,
                    "shards": 2,
                    "marker": "slow",
                    "collected": ["a", "b", "serial"],
                    "selected": selected,
                    "excluded": ["serial"],
                    "run": run,
                }
            )
        )
        paths.append(path)
    return paths


@pytest.mark.parametrize("duplicate", ["directory", "ID"])
def test_timing_refresh_rejects_duplicate_runs(
    tmp_path, monkeypatch, duplicate
) -> None:
    directories = []
    for index, seconds in enumerate((1, 4, 16)):
        directory = tmp_path / str(index)
        if duplicate == "directory":
            monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
            monkeypatch.delenv("GITHUB_RUN_ATTEMPT", raising=False)
        else:
            monkeypatch.setenv("GITHUB_RUN_ID", str(index // 2))
            monkeypatch.setenv("GITHUB_RUN_ATTEMPT", str(1 + index % 2))
        recorder = Recorder(directory / "timings.json")
        recorder.collected.add("a")
        recorder.finished.add("a")
        recorder.durations["a"] = seconds
        recorder.pytest_sessionfinish(0)
        directories.append(directory)

    destination = tmp_path / "snapshot.json"
    refresh(directories, ["a"], destination)
    assert load_durations(destination)["a"] == pytest.approx(4)
    unchanged = destination.read_bytes()

    repeated = directories[0]
    if duplicate == "ID":
        repeated = copytree(repeated, tmp_path / "copy")
    with pytest.raises(ValueError, match=f"duplicate timing run {duplicate}"):
        refresh([*directories, repeated], ["a"], destination)
    assert destination.read_bytes() == unchanged


def test_complete_shards_include_serial_exclusion(tmp_path) -> None:
    paths = evidence(tmp_path)
    check(paths, ["a", "b", "serial"], "slow", 2)


def test_timing_refresh_preserves_census_dates(tmp_path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    evidence(run)
    destination = tmp_path / "snapshot.json"
    collected = {"curation": "2026-10-06", "bf_derivatives": "2026-10-15"}
    destination.write_text(json.dumps({"collected": collected, "durations": {}}))
    refresh([run], ["a", "b", "serial"], destination)
    observed = json.loads(destination.read_text())["collected"]
    assert observed.pop("durations")
    assert observed == collected


def test_unroundable_timing_names_the_sample_and_preserves_the_snapshot(
    tmp_path, monkeypatch, capsys
) -> None:
    run = tmp_path / "run"
    run.mkdir()
    timings = run / "timings.json"
    recorder = Recorder(timings)
    recorder.collected.add("test_example")
    recorder.finished.add("test_example")
    recorder.durations["test_example"] = sys.float_info.max
    recorder.pytest_sessionfinish(0)
    artifact = json.loads(timings.with_suffix(".json.meta.json").read_text())[
        "durations_file"
    ]
    output = tmp_path / "snapshot.json"
    previous = b'{"collected": {"curation": "2026-10-06"}, "durations": {}}\n'
    output.write_bytes(previous)
    monkeypatch.setattr("scripts.ci.shard.collect_ids", lambda _: ["test_example"])

    with pytest.raises(SystemExit) as caught:
        refresh_main([str(run), "--output", str(output)])
    assert caught.value.code == 2
    message = capsys.readouterr().err
    assert str(run / artifact) in message
    assert "duration for 'test_example' cannot be rounded" in message
    assert output.read_bytes() == previous


@pytest.mark.parametrize(
    "malformed",
    ['{"collected": {"curation": "2026-10-06"},', '{"collected":{"curation": null}}'],
)
def test_timing_refresh_reports_and_preserves_invalid_snapshot(
    tmp_path, monkeypatch, capsys, malformed
) -> None:
    run = tmp_path / "run"
    run.mkdir()
    evidence(run)
    destination = tmp_path / "snapshot.json"
    destination.write_text(malformed, encoding="utf-8")
    monkeypatch.setattr(
        "scripts.ci.shard.collect_ids", lambda _marker: ["a", "b", "serial"]
    )
    with pytest.raises(SystemExit) as error:
        refresh_main([str(run), "--output", str(destination)])
    assert error.value.code == 2
    assert str(destination) in capsys.readouterr().err
    assert destination.read_text(encoding="utf-8") == malformed


def test_timing_load_parses_the_snapshot_it_hashed(tmp_path, monkeypatch) -> None:
    directory = evidence(tmp_path)[0].parent
    metadata = json.loads((directory / "test-durations.json.meta.json").read_text())
    snapshot = directory / metadata["durations_file"]
    replacement = tmp_path / "replacement.json"
    replacement.write_text('{"a": 900, "serial": 1}')
    read_bytes = Path.read_bytes

    def read_and_replace(path):
        data = read_bytes(path)
        if path == snapshot:
            replacement.replace(snapshot)
        return data

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "read_bytes", read_and_replace)
        assert load_run(directory, {"a", "serial"}) == {"a": 1, "serial": 1}
    with pytest.raises(ValueError, match="altered timing run"):
        load_run(directory, {"a", "serial"})


@pytest.mark.parametrize("variable", ["GITHUB_RUN_ID", "GITHUB_SHA"])
def test_shard_evidence_must_match_active_ci_run(tmp_path, monkeypatch, variable):
    monkeypatch.setenv("GITHUB_RUN_ID", "100")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    paths = evidence(tmp_path)
    check(paths, ["a", "b", "serial"], "slow", 2)

    monkeypatch.setenv(variable, "101" if variable == "GITHUB_RUN_ID" else "b" * 40)
    with pytest.raises(ValueError, match="differs from the active CI run"):
        check(paths, ["a", "b", "serial"], "slow", 2)
    monkeypatch.delenv("GITHUB_RUN_ID")
    monkeypatch.delenv("GITHUB_SHA")
    check(paths, ["a", "b", "serial"], "slow", 2)


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "index",
        "overlap",
        "omission",
        "corpus",
        "identity",
        "failed",
        "unfinished",
        "altered",
    ],
)
def test_bad_shard_evidence_fails_closed(tmp_path, fault) -> None:
    paths = evidence(tmp_path)
    manifest = json.loads(paths[1].read_text())
    if fault == "missing":
        paths.pop()
    elif fault == "index":
        manifest["shard"] = 0
    elif fault == "overlap":
        manifest["selected"] = ["a"]
    elif fault == "omission":
        manifest["selected"] = []
    elif fault == "corpus":
        manifest["collected"] = ["b"]
    elif fault == "identity":
        manifest["run"]["commit"] = "different"
    else:
        sidecar = paths[1].parent / "test-durations.json.meta.json"
        metadata = json.loads(sidecar.read_text())
        if fault == "failed":
            metadata["exitstatus"] = 1
        elif fault == "unfinished":
            metadata["finished"] = []
        else:
            (sidecar.parent / metadata["durations_file"]).write_text("{}")
        sidecar.write_text(json.dumps(metadata))
    if fault != "missing":
        paths[1].write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=r"shard|test|run|timing"):
        check(paths, ["a", "b", "serial"], "slow", 2)


@pytest.mark.medium
def test_real_shards_publish_complete_execution_evidence(tmp_path, monkeypatch) -> None:
    from pathlib import Path

    from scripts.ci import shard as pytest_shard

    (tmp_path / "test_example.py").write_text(
        "def test_one():\n    assert 1 + 1 == 2\n\n"
        "def test_two():\n    assert 2 + 2 == 4\n"
        "def test_serial():\n    assert 3 + 3 == 6\n"
    )
    monkeypatch.setattr(pytest_shard, "ROOT", tmp_path)
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[2]))
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k 'test_one or test_serial'")
    paths = []
    for index in range(2):
        directory = tmp_path / str(index)
        path = directory / "test.shard.json"
        assert (
            pytest_shard.shard_main(
                [
                    "--marker",
                    "not slow",
                    "--shard",
                    str(index),
                    "--shards",
                    "2",
                    "--manifest",
                    str(path),
                    "--exclude-node",
                    "test_example.py::test_serial",
                    "--",
                    "-q",
                    "-p",
                    "scripts.ci.shard",
                    "--duration-output",
                    str(directory / "durations.json"),
                ]
            )
            == 0
        )
        paths.append(path)
    corpus = pytest_shard.collect_ids("not slow")
    assert corpus == [
        "test_example.py::test_one",
        "test_example.py::test_serial",
        "test_example.py::test_two",
    ]
    with pytest.raises(ValueError, match="omit"):
        check(paths, corpus, "not slow", 2)
    monkeypatch.delenv("PYTEST_ADDOPTS")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "scripts.ci.shard",
            "--duration-output",
            str(paths[0].parent / "serial.json"),
            "test_example.py::test_serial",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        timeout=30,
    )
    check(paths, corpus, "not slow", 2)
