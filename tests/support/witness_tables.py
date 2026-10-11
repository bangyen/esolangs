"""Named truth tables that stand in for every table of an arity."""

import hashlib
import random


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


def dense(n: int, key: bytes | None = None) -> str:
    """A deterministic pseudo-random table, the worst case to fold.

    With ``key`` every arity extends the one below it; without, each
    arity draws its own bits.
    """
    digest = hashlib.sha256(key or f"dense:{n}".encode()).digest()
    bits: list[str] = []
    block = 0
    while len(bits) < 1 << n:
        digest = hashlib.sha256(digest + bytes([block & 255])).digest()
        bits.extend(str(byte & 1) for byte in digest)
        block += 1
    return "".join(bits[: 1 << n])


def nested_dense(n: int) -> str:
    """A dense table whose every arity extends the one below it."""
    return dense(n, b"nested-dense")
