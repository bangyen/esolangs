# ruff: noqa: SLF001 - exercise every construction, including unselected layouts.
"""Small constructions and deterministic wide truth tables."""

import importlib
import random
from functools import cache

builder = importlib.import_module("esolangs.tools.streetcode")


@cache
def sources(table):
    n = len(table).bit_length() - 1
    tree = builder._streetcode_tree(table)
    shared = builder._streetcode_shared_programs(table, n, tree)
    flat = builder._streetcode_flat(table, n)
    programs = [
        *shared,
        builder._streetcode_hallway_program(n, tree),
        flat,
        builder._streetcode_quarter_turn(flat),
        builder._streetcode_quarter_turn(builder._streetcode_shared_kerb(flat)),
    ]
    programs += [builder._streetcode_rotate(source) for source in programs[:]]
    programs += [builder.streetcode(table, width) for width in (4, 7, 8, 9, 25, 29, 33)]
    return set(programs)


def tables(n):
    size = 1 << n
    rng = random.Random(78016 + n)
    points = {0, size // 3, size - 1}
    return {
        "zero": "0" * size,
        "one": "1" * size,
        "parity": "".join(str(row.bit_count() % 2) for row in range(size)),
        "sparse": "".join(str(int(row in points)) for row in range(size)),
        "dense": "".join(str(int(row not in points)) for row in range(size)),
        "random": "".join(rng.choice("01") for _ in range(size)),
    }
