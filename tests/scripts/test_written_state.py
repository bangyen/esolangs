"""``WrittenState`` counts written snapshot parts whole and skips read-only ones."""

import pytest

from scripts.benchmark import WrittenState


def test_read_only_parts_are_excluded() -> None:
    code = "+" * 1000
    state = WrittenState((code, 0))
    state.sample((code, 5))
    assert state.bits == 3


def test_a_written_store_counts_whole_at_its_peak() -> None:
    state = WrittenState(((0,) * 8, 0))
    state.sample(((1,) + (0,) * 7, 0))
    state.sample(((0,) * 8, 0))
    assert state.bits == 8


def test_an_equal_rebuild_is_not_a_write() -> None:
    state = WrittenState((tuple(range(4)), 0))
    state.sample((tuple(range(4)), 0))
    assert state.bits == 0


def test_a_reshaped_snapshot_aborts() -> None:
    state = WrittenState((0, 0))
    with pytest.raises(ValueError, match="shape"):
        state.sample((0,))
