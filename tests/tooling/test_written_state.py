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


def test_mixed_records_keep_scalar_widths_and_mutable_counts() -> None:
    from fractions import Fraction

    from scripts.benchmark import state_bits

    record = (("x", -8), ("y", 0), ("z", 1.5), ("q", Fraction(-3, 4)))
    assert state_bits(record, {}) == 32 + 5 + 1 + 64 + 3 + 3
    mutable = [record, bytearray(b"ab"), True, None]
    assert state_bits(mutable, {}) == 32 + 5 + 1 + 64 + 3 + 3 + 16 + 1
    mutable.append(256)
    assert state_bits(mutable, {}) == 32 + 5 + 1 + 64 + 3 + 3 + 16 + 1 + 9


def test_flat_integer_delta_retains_whole_store_peak() -> None:
    initial = (0,) * 32
    state = WrittenState((initial,))
    state.sample(((1000, *initial[1:]),))
    assert state.bits == 41
    changed = list(initial)
    changed[2] = -1024
    state.sample((tuple(changed),))
    assert state.bits == 43
    state.sample((initial,))
    assert state.bits == 43
