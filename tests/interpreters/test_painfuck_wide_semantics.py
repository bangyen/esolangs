"""Wide emitted programs checked against independent transitions."""

import random
from functools import lru_cache

import pytest

from esolangs.tools.painfuck import painfuck
from tests.interpreters.painfuck_observer import check


@lru_cache(maxsize=4)
def source_table(n, family):
    count = 1 << n
    exceptions = {0, count // 3, count - 1}
    rng = random.Random(103549 + n)
    tables = {
        "zero": "0" * count,
        "one": "1" * count,
        "parity": "".join(str(row.bit_count() % 2) for row in range(count)),
        "sparse": "".join(str(int(row in exceptions)) for row in range(count)),
        "dense": "".join(str(int(row not in exceptions)) for row in range(count)),
        "random": "".join(rng.choice("01") for _ in range(count)),
    }
    table = tables[family]
    return (painfuck(table), table)


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "family", "start"),
    [
        (n, family, start)
        for n in range(4, 11)
        for family in ("zero", "one", "parity", "sparse", "dense", "random")
        for start in range(0, 1 << n, 8)
    ],
)
def test_wide_rows(n, family, start):
    source, table = source_table(n, family)
    for row in range(start, start + 8):
        result = check(source, " ".join(format(row, f"0{n}b")))
        assert result["halted"]
        assert result["output"] == table[row]
        assert result["reads"] == n
