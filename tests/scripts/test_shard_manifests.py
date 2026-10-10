"""Shard evidence proves successful, exactly-once execution of fresh collection."""

import json

import pytest

from checks.check_shard_manifests import check
from scripts.pytest_durations import Recorder


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


def test_complete_shards_include_serial_exclusion(tmp_path):
    paths = evidence(tmp_path)
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
def test_bad_shard_evidence_fails_closed(tmp_path, fault):
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
def test_real_shards_publish_complete_execution_evidence(tmp_path, monkeypatch):
    from pathlib import Path

    from scripts import pytest_shard

    (tmp_path / "test_example.py").write_text(
        "def test_one():\n    assert 1 + 1 == 2\n\n"
        "def test_two():\n    assert 2 + 2 == 4\n"
    )
    monkeypatch.setattr(pytest_shard, "ROOT", tmp_path)
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[2]))
    paths = []
    for index in range(2):
        directory = tmp_path / str(index)
        path = directory / "test.shard.json"
        assert (
            pytest_shard.main(
                [
                    "--marker",
                    "not slow",
                    "--shard",
                    str(index),
                    "--shards",
                    "2",
                    "--manifest",
                    str(path),
                    "--",
                    "-q",
                    "-p",
                    "scripts.pytest_durations",
                    "--duration-output",
                    str(directory / "durations.json"),
                ]
            )
            == 0
        )
        paths.append(path)
    check(paths, pytest_shard.collect_ids("not slow"), "not slow", 2)
