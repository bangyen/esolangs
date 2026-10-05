"""Every heading and row in the completed wide LaserFuck corpus."""

import random
from functools import cache

import pytest

from esolangs.tools.laserfuck import laserfuck
from tests.interpreters.laserfuck_observer import check


@cache
def table_for(n, family):
    size = 1 << n
    if family == "zero":
        return "0" * size
    if family == "one":
        return "1" * size
    if family == "parity":
        return "".join(str(i.bit_count() % 2) for i in range(size))
    if family == "sparse":
        return "".join(
            "1" if i in (0, size - 1, size // 2) else "0" for i in range(size)
        )
    if family == "dense":
        return "".join(
            "0" if i in (0, size - 1, size // 2) else "1" for i in range(size)
        )
    rng = random.Random(1000 + n)
    return "".join(rng.choice("01") for _ in range(size))


@cache
def source_for(n, family, width):
    return laserfuck(table_for(n, family), width)


CASES = []
for n in range(4, 11):
    for family in ("zero", "one", "parity", "sparse", "dense", "random"):
        sources = {}
        for width in (None, 1, 13, 100):
            sources.setdefault(source_for(n, family, width), width)
        for width in sources.values():
            for heading in range(4):
                for row in range(1 << n):
                    CASES.append((n, family, width, heading, row))


@pytest.mark.medium
@pytest.mark.parametrize(("n", "family", "width", "heading", "row"), CASES)
def test_every_wide_input(n, family, width, heading, row):
    output, _ = check(source_for(n, family, width), format(row, f"0{n}b"), heading)
    assert output == table_for(n, family)[row]
