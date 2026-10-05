"""Every row of the independent wide Flowchart corpus."""

import random
from functools import cache, lru_cache

import pytest

from esolangs.interpreters.grid_based.flowchart import _Machine
from esolangs.tools.flowchart import flowchart
from tests.interpreters.flowchart_observer import Factory


@cache
def table_for(n, family):
    count = 1 << n
    exceptions = {0, count // 3, count - 1}
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
    rng = random.Random(175580 + n)
    return "".join(str(rng.randrange(2)) for _ in range(count))


@lru_cache(maxsize=4)
def factory_for(n, family, width):
    return Factory(flowchart(table_for(n, family), width).splitlines(), _Machine)


CASES = []
for n in range(4, 11):
    for family in ("zero", "one", "parity", "sparse", "dense", "random"):
        sources = {}
        for width in (None, 1, 13, 100):
            sources.setdefault(flowchart(table_for(n, family), width), width)
        for width in sources.values():
            stride = 1 if n >= 8 else 8
            for first in range(0, 1 << n, stride):
                CASES.append((n, family, width, first, stride))


@pytest.mark.medium
@pytest.mark.parametrize(("n", "family", "width", "first", "stride"), CASES)
def test_every_wide_input(n, family, width, first, stride):
    table = table_for(n, family)
    factory = factory_for(n, family, width)
    for row in range(first, min(first + stride, 1 << n)):
        result = factory.check(format(row, f"0{n}b"), table[row])
        assert result["halted"]
        assert result["reads"] == n
