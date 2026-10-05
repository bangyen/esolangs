"""Every input of the independently executed wide Packlang corpus."""

import random
from functools import cache

import pytest

from esolangs.tools.packlang import packlang
from tests.interpreters.packlang_observer import check


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
    rng = random.Random(71377 + n)
    return "".join(str(rng.randrange(2)) for _ in range(count))


@cache
def source_for(n, family, width):
    return packlang(table_for(n, family), width)


CASES = []
for n in range(4, 11):
    for family in ("zero", "one", "parity", "sparse", "dense", "random"):
        for width in (None, 1, 13, 100):
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
        assert result["output"] == table[row]
        assert result["reads"] == n
