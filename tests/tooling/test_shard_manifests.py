"""Shard evidence proves successful, exactly-once execution of fresh collection."""

import json
import subprocess
import sys

import pytest

from checks.check_shard_manifests import check
from scripts.ci.shard import Recorder


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


def test_complete_shards_include_serial_exclusion(tmp_path) -> None:
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
    with pytest.raises(ValueError, match="omit"):
        check(paths, corpus, "not slow", 2)
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


@pytest.mark.medium
def test_folded_size_case_still_publishes_execution_evidence(tmp_path) -> None:
    """A size case folded into its workspace pair still counts as executed.

    The proofs conftest folds a size case into the paired workspace case
    when both are selected; the size node skips instead of disappearing,
    so the shard manifest's selection and the run's evidence still agree.
    Run 45922204043 failed the completeness gate on 98 such cases, all
    deselected at collection time by the fold.
    """
    import os
    from pathlib import Path

    from tests.proofs._witnesses import _WITNESS_BAND
    from tests.proofs.execution import FORMULAS as EXECUTION_FORMULAS
    from tests.proofs.test_scaling_formulas import FORMULAS as SCALING
    from tests.proofs.test_workspace_formulas import (
        _SLOW_AT_MIN,
        _first_above_two,
        _formula_cases,
    )
    from tests.proofs.workspace import FORMULAS as WORKSPACE_FORMULAS

    ledgers = (EXECUTION_FORMULAS, WORKSPACE_FORMULAS)
    workspace = {(param.values[0], param.values[1]) for param in _formula_cases()}

    def folds(name: str, n: int) -> bool:
        # The hook only pairs cases neither band marks slow nor weekly.
        if _WITNESS_BAND.get((name, n)) == "weekly":
            return False
        if (name, n) in _SLOW_AT_MIN:
            return False
        return n <= 2 or any(
            name in ledger and n == _first_above_two(ledger[name][2])
            for ledger in ledgers
        )

    pair = next(
        (name, n)
        for name in sorted(SCALING)
        for n in SCALING[name][2]
        if (name, n) in workspace and folds(name, n)
    )
    size = (
        "tests/proofs/test_scaling_formulas.py::"
        f"test_size_formulas_hold[{pair[0]}-{pair[1]}]"
    )
    workspace_node = (
        "tests/proofs/test_workspace_formulas.py::"
        f"test_execution_and_workspace_formulas_hold[{pair[0]}-{pair[1]}]"
    )
    durations = tmp_path / "durations.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-n",
            "0",
            "-p",
            "scripts.ci.shard",
            "--duration-output",
            str(durations),
            size,
            workspace_node,
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed, 1 skipped" in result.stdout
    metadata = json.loads(durations.with_suffix(".json.meta.json").read_text())
    assert metadata["collected"] == sorted([size, workspace_node])
    assert metadata["finished"] == metadata["collected"]
    durations_map = json.loads(durations.read_text())
    assert set(durations_map) == {size, workspace_node}
    assert all(seconds > 0 for seconds in durations_map.values())
