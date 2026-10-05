"""Independent execution of every wide Modulous corpus row."""

import random
from functools import cache, lru_cache

import pytest

from esolangs.tools.modulous import modulous
from tests.interpreters.modulous_observer import check


@cache
def table_for(n, family):
    count = 1 << n
    exceptions = {0, count - 1, count // 2}
    if family == "zero":
        return "0" * count
    if family == "one":
        return "1" * count
    if family == "parity":
        return "".join(str(row.bit_count() % 2) for row in range(count))
    if family == "sparse":
        return "".join(str(int(row in exceptions)) for row in range(count))
    if family == "dense":
        return "".join(str(int(row not in exceptions)) for row in range(count))
    rng = random.Random(1000 + n)
    return "".join(rng.choice("01") for _ in range(count))


@lru_cache(maxsize=4)
def source_for(n, family, width):
    return modulous(table_for(n, family), width)


CASES = []
for n in range(4, 11):
    stride = 8 if n < 8 else 1
    for family in ("zero", "one", "parity", "sparse", "dense", "random"):
        for width in (None, 1, 13, 100):
            for first in range(0, 1 << n, stride):
                CASES.append((n, family, width, first, stride))


@pytest.mark.medium
@pytest.mark.parametrize(("n", "family", "width", "first", "stride"), CASES)
def test_every_wide_row(n, family, width, first, stride):
    table = table_for(n, family)
    source = source_for(n, family, width)
    for row in range(first, min(first + stride, 1 << n)):
        result = check(source, " ".join(format(row, f"0{n}b")), limit=10000)
        assert result["halted"]
        assert result["error"] is None
        assert result["output"] == table[row]
        assert result["reads"] == n
