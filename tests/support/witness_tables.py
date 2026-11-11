"""Named truth tables that stand in for every table of an arity."""

import random

from scripts.docs.evidence import dense as dense


def witnesses(n: int) -> list[str]:
    """Return the distinct witness tables for ``n`` inputs."""
    size = 1 << n
    tables = [
        "0" * size,
        "1" * size,
        "0" * (size - 1) + "1",
        "0" * (size // 2) + "1" * (size // 2),
        parity(n),
        format(random.Random(n).getrandbits(size), f"0{size}b"),
    ]
    return list(dict.fromkeys(tables))


def row_bits(row: int, n: int) -> list[int]:
    """A table row's ``n`` input bits, most significant first."""
    return [row >> (n - 1 - i) & 1 for i in range(n)]


def parity(n: int) -> str:
    """The ``n``-input parity table: every input matters at every row."""
    return "".join(str(row.bit_count() & 1) for row in range(1 << n))


def nested_dense(n: int) -> str:
    """A dense table whose every arity extends the one below it."""
    return dense(n, b"nested-dense")


def _drawing(template: str) -> str:
    """The template as the drawing the reorder bar compares."""
    return template


def _one_minterm(n: int) -> str:
    """A single 1, which makes every input essential at minimum size."""
    return "1" + "0" * (2**n - 1)


XOR = "0110"


#: Every one- and two-input table, in numeric order within each arity.
SMALL_TABLES = tuple(format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n))


def split_residuals(n: int) -> int:
    """Most distinct split residuals: differing halves at each depth."""
    return sum(
        min(2**d, 2 ** (2 ** (n - d)) - 2 ** (2 ** (n - d - 1))) for d in range(n)
    )


def second_last_zero(n: int) -> str:
    """Return the table whose only zero is the penultimate row."""
    return "1" * ((1 << n) - 2) + "01"
