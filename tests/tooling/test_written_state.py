"""``WrittenState`` counts written snapshot parts whole and skips read-only ones."""

import pytest

from esolangs.runtime._state import WorkspaceModel
from scripts.benchmark import WrittenState

_PAIR = WorkspaceModel("pair-test-v1", ("store", "cursor"))
_STORE = WorkspaceModel("store-test-v1", ("store",))


def test_read_only_parts_are_excluded() -> None:
    code = "+" * 1000
    state = WrittenState(_PAIR.capture(store=code, cursor=0))
    state.sample(_PAIR.capture(store=code, cursor=5))
    assert state.bits == 3


def test_a_written_store_counts_whole_at_its_peak() -> None:
    state = WrittenState(_PAIR.capture(store=(0,) * 8, cursor=0))
    state.sample(_PAIR.capture(store=(1,) + (0,) * 7, cursor=0))
    state.sample(_PAIR.capture(store=(0,) * 8, cursor=0))
    assert state.bits == 8


def test_an_equal_rebuild_is_not_a_write() -> None:
    state = WrittenState(_PAIR.capture(store=tuple(range(4)), cursor=0))
    state.sample(_PAIR.capture(store=tuple(range(4)), cursor=0))
    assert state.bits == 0


def test_a_reshaped_snapshot_aborts() -> None:
    state = WrittenState(_PAIR.capture(store=0, cursor=0))
    with pytest.raises(ValueError, match="model changed"):
        state.sample(_STORE.capture(store=0))


@pytest.mark.parametrize("raw", [(0, 0), 0, None])
def test_raw_values_cannot_enable_snapshot_accounting(raw) -> None:
    with pytest.raises(TypeError, match="WorkspaceSnapshot"):
        WrittenState(raw)
    state = WrittenState(_PAIR.capture(store=0, cursor=0))
    with pytest.raises(TypeError, match="WorkspaceSnapshot"):
        state.sample(raw)


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
    state = WrittenState(_STORE.capture(store=initial))
    state.sample(_STORE.capture(store=(1000, *initial[1:])))
    assert state.bits == 41
    changed = list(initial)
    changed[2] = -1024
    state.sample(_STORE.capture(store=tuple(changed)))
    assert state.bits == 43
    state.sample(_STORE.capture(store=initial))
    assert state.bits == 43
