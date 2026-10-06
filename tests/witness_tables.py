"""Named truth tables that stand in for every table of an arity."""

import random


def witnesses(n: int) -> list[str]:
    """Return the distinct witness tables for ``n`` inputs."""
    size = 1 << n
    tables = [
        "0" * size,
        "1" * size,
        "0" * (size - 1) + "1",
        "0" * (size // 2) + "1" * (size // 2),
        "".join(str(row.bit_count() % 2) for row in range(size)),
        format(random.Random(n).getrandbits(size), f"0{size}b"),
    ]
    return list(dict.fromkeys(tables))
