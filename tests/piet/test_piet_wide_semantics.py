"""Wide emitted Piet rasters checked against independent transitions."""

import random
from functools import lru_cache

import pytest

from esolangs.tools.piet import piet
from tests.piet.test_piet_semantics import compare_execution


@lru_cache(maxsize=4)
def source_table(n, family, width):
    count = 1 << n
    rng = random.Random(20180927 + n)
    exceptions = {0, count // 3, count - 1}
    tables = {
        "zero": "0" * count,
        "one": "1" * count,
        "parity": "".join(str(row.bit_count() % 2) for row in range(count)),
        "sparse": "".join(str(int(row in exceptions)) for row in range(count)),
        "dense": "".join(str(int(row not in exceptions)) for row in range(count)),
        "random": "".join(rng.choice("01") for _ in range(count)),
    }
    table = tables[family]
    return piet(table, width), table


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "family", "width", "start"),
    [
        (n, family, width, start)
        for n in range(4, 11)
        for family in ("zero", "one", "parity", "sparse", "dense", "random")
        for width in (None, 20, 40)
        for start in range(0, 1 << n, 1 if n >= 8 else 8)
    ],
)
def test_wide_rows(n, family, width, start):
    program, table = source_table(n, family, width)
    for row in range(start, start + (1 if n >= 8 else 8)):
        result = compare_execution(program, " ".join(format(row, f"0{n}b")), 1, 100000)
        assert result.state[4]
        assert result.output == table[row]
        assert result.reads == n
