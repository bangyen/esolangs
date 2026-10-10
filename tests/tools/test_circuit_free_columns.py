"""Column reuse preserves threshold queries and discarded slots."""

import pytest

from esolangs.tools.circuit_diagram.free_columns import _FreeColumns


@pytest.mark.parametrize("mask", range(32))
def test_queries_return_the_leftmost_eligible_column_without_consuming(mask):
    free = _FreeColumns()
    expected = {column for column in range(5) if mask & (1 << column)}
    for column in sorted(expected, reverse=True):
        free.add(column)
        free.add(column)
    for threshold in range(-2, 7):
        answer = min(
            (column for column in expected if column > threshold), default=None
        )
        assert free.first_after(threshold) == answer
    for column in range(5):
        free.discard(column)
        expected.discard(column)
        assert free.first_after(-1) == min(expected, default=None)


def test_growth_keeps_ineligible_columns_available_for_later_reads():
    free = _FreeColumns()
    for column in (1, 7, 1024):
        free.add(column)
    assert free.first_after(3) == 7
    free.discard(7)
    assert free.first_after(3) == 1024
    assert free.first_after(-1) == 1
    free.discard(-1)
    free.discard(2048)
    free.clear()
    assert free.first_after(-1) is None
    free.add(3)
    assert free.first_after(2) == 3


def test_negative_columns_are_rejected():
    with pytest.raises(ValueError, match="nonnegative"):
        _FreeColumns().add(-1)
