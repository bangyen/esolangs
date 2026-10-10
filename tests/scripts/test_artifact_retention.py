"""Pruning keeps completed timing evidence and ignores unrelated files."""

import json
import os

import pytest

from scripts.prune_artifacts import candidates, main


def test_retention_is_dry_by_default_and_keeps_references(tmp_path):
    kept = tmp_path / f"timings.json.{'a' * 64}.json"
    expired = tmp_path / f"timings.json.{'b' * 64}.json"
    unrelated = tmp_path / "important.log"
    recent = tmp_path / f"timings.json.{'c' * 64}.json"
    log = tmp_path / "notes/benchmarks/worker.log"
    log.parent.mkdir(parents=True)
    for path in (kept, expired, unrelated, log, recent):
        path.write_text("evidence")
        os.utime(path, (1, 1))
    os.utime(recent, (100000, 100000))
    (tmp_path / "timings.json.meta.json").write_text(
        json.dumps({"durations_file": kept.name})
    )
    assert candidates(tmp_path, 1, 100000) == sorted([expired, log])
    main(["--root", str(tmp_path), "--days", "30"])
    assert expired.exists()
    assert log.exists()
    main(["--root", str(tmp_path), "--days", "30", "--apply"])
    assert not expired.exists()
    assert not log.exists()
    assert kept.exists()
    assert unrelated.exists()


def test_corrupt_sidecar_blocks_pruning(tmp_path):
    path = tmp_path / "timings.json.meta.json"
    path.write_text("invalid")
    with pytest.raises(ValueError, match="Expecting value"):
        candidates(tmp_path, 0, 100000)


@pytest.mark.parametrize("days", [-1, float("nan"), float("inf")])
def test_invalid_retention_rejected(tmp_path, days):
    with pytest.raises(ValueError, match="days"):
        candidates(tmp_path, days, 100000)
