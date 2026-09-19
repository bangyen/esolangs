"""One shard of a marker band runs its slice and no one else's."""

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "pytest_shard.py"


def load_script() -> object:
    """Import the sharder as a module, mirroring the other script tests."""
    spec = importlib.util.spec_from_file_location("pytest_shard", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
            shard.main(["--marker", "slow", "--shard", "4", "--shards", "4"])  # type: ignore[attr-defined]

    def test_an_empty_slice_exits_clean_without_running_pytest(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fewer tests than shards is not a failure in any of them."""
        shard = load_script()
        monkeypatch.setattr(shard, "collect_ids", lambda _marker: [])  # type: ignore[attr-defined]
        assert shard.main(["--marker", "slow", "--shard", "3", "--shards", "4"]) == 0  # type: ignore[attr-defined]
