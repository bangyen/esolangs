"""One shard of a marker band runs its slice and no one else's."""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.tooling.script_support import load

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "shard.py"


def load_script() -> Any:
    return load(SCRIPT)


class TestShardIds:
    """Round-robin covers everything exactly once."""

    def test_four_shards_partition(self) -> None:
        shard = load_script()
        ids = [f"tests/t.py::test_{i}" for i in range(10)]
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


@pytest.mark.parametrize("payload", ["[]", '{"a": -1}', '{"a": true}', '{"a": NaN}'])
def test_bad_durations_are_refused(tmp_path, payload) -> None:
    path = tmp_path / "durations.json"
    path.write_text(payload)
    with pytest.raises(ValueError, match="finite positive"):
        load_script().load_durations(path)


def test_invalid_shard_arguments_are_refused() -> None:
    with pytest.raises(ValueError, match="invalid shard"):
        load_script().shard_ids([], -1, 2)


def test_shard_reports_estimate_and_unknown_weights(
    tmp_path, monkeypatch, capsys
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
            ]
        )
        == 0
    )
    assert "18.0s (1 tests use median fallback 6.000s)" in capsys.readouterr().out


def test_duration_order_uses_read_only_input_and_preserves_fixture_order(
    tmp_path,
) -> None:
    from types import SimpleNamespace

    shard = load_script()
    source = tmp_path / "durations.json"
    source.write_text('{"a.py::second": 20, "b.py::first": 1}')
    options = {
        "duration_input": source,
        "duration_output": None,
        "duration_order": True,
    }
    config = SimpleNamespace(stash={}, getoption=options.__getitem__)
    shard.pytest_configure(config)
    items = [
        SimpleNamespace(nodeid=node)
        for node in ("b.py::first", "a.py::first", "a.py::second", "new.py::first")
    ]
    shard.pytest_collection_modifyitems(config, items)
    assert [item.nodeid for item in items] == [
        "a.py::first",
        "a.py::second",
        "b.py::first",
        "new.py::first",
    ]
    assert source.read_text() == '{"a.py::second": 20, "b.py::first": 1}'


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
