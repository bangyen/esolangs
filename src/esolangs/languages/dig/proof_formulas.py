"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    count: int = (
        128 + 46 * 2 ** ((n - 6) // 2) if n % 2 == 0 else 128 + 64 * 2 ** ((n - 7) // 2)
    )
    return count


def _dig(n: int, p: str) -> int:
    """The R by C grid at a byte a cell, its two coordinates, two counters."""
    bl = int.bit_length
    lines = p.split("\n")
    rows, cols = len(lines), max(map(len, lines))
    return 8 * rows * cols + bl(rows - 1) + bl(cols - 1) + bl(2 * n - 1) + bl(n) + 10


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    return _dig(n, p)
