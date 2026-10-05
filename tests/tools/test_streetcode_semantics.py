"""Execute all finite small constructions and wide truth-table rows."""

from functools import cache

import pytest

from esolangs.tools.streetcode import streetcode
from tests.tools.streetcode_cases import sources, tables
from tests.tools.streetcode_observer import check


@cache
def emitted(table):
    return {streetcode(table, width) for width in (None, 1, 13, 100)}


@pytest.mark.medium
@pytest.mark.parametrize(
    ("table", "start"),
    [
        (table, start)
        for table in [
            format(index, f"0{1 << n}b")
            for n in range(1, 4)
            for index in range(1 << (1 << n))
        ]
        + ["1000000000000000", format(0x9466E472, "032b")]
        + [
            "".join(str((value * 73 + value // 3) & 1) for value in range(1 << n))
            for n in (5, 6)
        ]
        for start in range(0, len(table), 2)
    ],
)
def test_small_constructions(table, start):
    for source in sources(table):
        for row in range(start, min(start + 2, len(table))):
            check(source, table, row)


@pytest.mark.medium
@pytest.mark.parametrize(
    ("table", "start"),
    [
        (table, start)
        for n in range(4, 11)
        for table in tables(n).values()
        for start in range(0, len(table), 4)
    ],
)
def test_wide_generated_rows(table, start):
    for source in emitted(table):
        for row in range(start, min(start + 4, len(table))):
            check(source, table, row)


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "width", "row"),
    [
        (n, width, row)
        for n in (7, 8, 11)
        for width in (None, 1)
        for row in (0, (1 << n) // 2, (1 << n) - 1)
    ],
)
def test_growth_execution_controls(n, width, row):
    table = "".join(str(index.bit_count() & 1) for index in range(1 << n))
    check(streetcode(table, width), table, row)
