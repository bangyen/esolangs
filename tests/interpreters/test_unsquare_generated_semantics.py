"""Exhaustive small-table execution with independent Unsquare state checks."""

import pytest

from esolangs import generate
from tests.interpreters.unsquare_observer import check


@pytest.mark.parametrize(
    ("n", "value"), [(n, value) for n in (1, 2, 3) for value in range(1 << (1 << n))]
)
def test_every_small_table(n, value):
    table = format(value, f"0{1 << n}b")
    for source in {generate("Unsquare", table, width) for width in (None, 1, 13, 100)}:
        for row, answer in enumerate(table):
            result = check(source, format(row, f"0{n}b"))
            assert result["halted"]
            assert result["error"] is None
            assert result["output"] == answer
            assert result["reads"] == n
