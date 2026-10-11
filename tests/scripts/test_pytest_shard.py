"""One shard of a marker band runs its slice and no one else's."""

from pathlib import Path
from typing import Any

import pytest

from tests.scripts.script_support import load

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ci.py"


def load_script() -> Any:
    return load(SCRIPT)


class TestShardIds:
    """Round-robin covers everything exactly once."""

    def test_four_shards_partition(self) -> None:
        shard = load_script()
        ids = [f"tests/t.py::test_{i}" for i in range(10)]
        parts = [shard.shard_ids(ids, i, 4) for i in range(4)]  # type: ignore[attr-defined]
        assert sorted(n for part in parts for n in part) == ids
        assert len({n for part in parts for n in part}) == len(ids)

    def test_more_shards_than_tests_leaves_empties(self) -> None:
        shard = load_script()
        ids = ["tests/t.py::test_0"]
        assert shard.shard_ids(ids, 0, 4) == ids  # type: ignore[attr-defined]
        assert shard.shard_ids(ids, 3, 4) == []  # type: ignore[attr-defined]

    def test_out_of_range_shard_is_rejected(self) -> None:
        shard = load_script()
        with pytest.raises(SystemExit):
            shard.shard_main(["--marker", "slow", "--shard", "4", "--shards", "4"])  # type: ignore[attr-defined]

    def test_an_empty_slice_exits_clean_without_running_pytest(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fewer tests than shards is not a failure in any of them."""
        shard = load_script()
        monkeypatch.setattr(shard, "collect_ids", lambda _marker: [])  # type: ignore[attr-defined]
        assert (
            shard.shard_main(["--marker", "slow", "--shard", "3", "--shards", "4"]) == 0
        )  # type: ignore[attr-defined]


def test_duration_assignment_improves_longest_shard_and_covers_unknowns():
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
def test_bad_durations_are_refused(tmp_path, payload):
    path = tmp_path / "durations.json"
    path.write_text(payload)
    with pytest.raises(ValueError, match="finite positive"):
        load_script().load_durations(path)


def test_invalid_shard_arguments_are_refused():
    with pytest.raises(ValueError, match="invalid shard"):
        load_script().shard_ids([], -1, 2)


def test_shard_reports_estimate_and_unknown_weights(tmp_path, monkeypatch, capsys):
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
