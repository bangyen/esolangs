"""Execute emitted Vandevelo against independent termination semantics."""

from functools import cache

import pytest

from esolangs.tools.vandevelo import vandevelo
from tests.interpreters import vandevelo_observer as probe
from tests.interpreters.vandevelo_cases import tables


@cache
def emitted(table, width):
    return vandevelo(table, width)


@pytest.mark.parametrize(
    "table",
    [
        format(index, f"0{1 << n}b")
        for n in range(1, 4)
        for index in range(1 << (1 << n))
    ],
)
def test_generated_table(table):
    n = len(table).bit_length() - 1
    source = vandevelo(table)
    for row, answer in enumerate(table):
        values = list(format(row, f"0{n}b"))
        _, reads, outcome = probe.reference(source, values)
        assert reads == n
        assert outcome == ("cycle" if answer == "1" else None)
        probe.check(source, values)


@pytest.mark.medium
@pytest.mark.parametrize(
    ("table", "width", "start"),
    [
        (table, width, start)
        for n in range(4, 11)
        for table in tables(n).values()
        for width in (None, 1)
        for start in range(0, len(table), 4)
    ],
)
def test_wide_generated_rows(table, width, start):
    n = len(table).bit_length() - 1
    source = emitted(table, width)
    for row in range(start, min(start + 4, len(table))):
        values = list(format(row, f"0{n}b"))
        _, reads, outcome = probe.reference(source, values)
        assert reads == n
        assert outcome == ("cycle" if table[row] == "1" else None)
        probe.check(source, values)
