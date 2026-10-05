"""Named truth-table families used by the independent audit."""

import random


def tables(n):
    size = 1 << n
    rng = random.Random(75287 + n)
    points = {0, size // 3, size - 1}
    return {
        "zero": "0" * size,
        "one": "1" * size,
        "parity": "".join(str(row.bit_count() % 2) for row in range(size)),
        "sparse": "".join(str(int(row in points)) for row in range(size)),
        "dense": "".join(str(int(row not in points)) for row in range(size)),
        "random": "".join(rng.choice("01") for _ in range(size)),
    }
