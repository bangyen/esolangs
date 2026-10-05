"""Deterministic Piet raster and stack comparison cases."""

import itertools
import random

from tests.piet.piet_raster import BLACK, PALETTE, WHITE


def raster_case(seed, *, execution=False):
    rng = random.Random((103549 if execution else 175580) + seed)
    w = rng.randrange(1, 7)
    h = rng.randrange(1, 7)
    rows = tuple(
        tuple(rng.choice([*PALETTE, WHITE, BLACK, (1, 2, 3)]) for _ in range(w))
        for _ in range(h)
    )
    if execution:
        return (rows, rng.choice(["", "3 -2 0", "nope 7", "λ\n🙂", "5 2 1 0"]))
    point = (rng.randrange(w), rng.randrange(h))
    stack = tuple(rng.randrange(-5, 6) for _ in range(rng.randrange(7)))
    return (rows, point, stack)


def stacks():
    return [
        stack
        for length in range(6)
        for stack in itertools.product(range(-2, 3), repeat=length)
    ]


def legacy_tables():
    rng = random.Random(20261001)
    result = []
    for n in (4, 5, 6):
        tables = ["".join(rng.choice("01") for _ in range(1 << n)) for _ in range(12)]
        for selected in (0, (1 << n) - 1, (1 << n) // 3):
            table = "".join(str(int(row == selected)) for row in range(1 << n))
            tables.extend((table, table.translate(str.maketrans("01", "10"))))
        result.extend((n, table) for table in tables)
    return result
