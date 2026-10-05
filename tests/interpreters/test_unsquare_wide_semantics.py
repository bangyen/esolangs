"""Every input in the independent wide Unsquare corpus."""

import random
from functools import cache

import pytest

from esolangs import generate
from tests.interpreters.unsquare_observer import check


@cache
def table_for(n, family):
    size = 1 << n
    exceptions = {0, size // 3, size - 1}
    if family == "zero":
        return "0" * size
    if family == "one":
        return "1" * size
    if family == "parity":
        return "".join(str(row.bit_count() % 2) for row in range(size))
    if family == "sparse":
        return "".join(str(int(row in exceptions)) for row in range(size))
    if family == "dense":
        return "".join(str(int(row not in exceptions)) for row in range(size))
    rng = random.Random(67140 + n)
    return "".join(str(rng.randrange(2)) for _ in range(size))


@cache
def source_for(n, family, width):
    return generate("Unsquare", table_for(n, family), width)


CASES = []
for n in range(4, 11):
    for family in ("zero", "one", "parity", "sparse", "dense", "random"):
        sources = {}
        for width in (None, 1, 13, 100):
            sources.setdefault(source_for(n, family, width), width)
        for width in sources.values():
            stride = 1 if n >= 8 else 8
            for first in range(0, 1 << n, stride):
                CASES.append((n, family, width, first, stride))


@pytest.mark.medium
@pytest.mark.parametrize(("n", "family", "width", "first", "stride"), CASES)
def test_every_wide_input(n, family, width, first, stride):
    table = table_for(n, family)
    source = source_for(n, family, width)
    for row in range(first, min(first + stride, 1 << n)):
        result = check(source, format(row, f"0{n}b"))
        assert result["halted"]
        assert result["error"] is None
        assert result["output"] == table[row]
        assert result["reads"] == n
