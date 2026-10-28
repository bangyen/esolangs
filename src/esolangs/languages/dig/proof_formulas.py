"""Executed command and snapshot-bit bounds."""

#: The indexed decoder's walk: its entry, prefix decoder and descent, and
#: shared body (+ 24 per class past the first), at the most classes the
#: prefix can label -- min(10, 2^(n-6)).  Defined at n = 8..12 only.
_INDEXED = {8: 265, 9: 371, 10: 435, 11: 539, 12: 561}


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program.

    An unshared tree walks at most 128 + 46*2^((n-6)/2) (even n) or
    128 + 64*2^((n-7)/2) (odd).  A shared leaf adds one travel along an
    axis of the grid, 28*2^((n-6)/2) - 3 or 28*2^((n-7)/2) - 3 cells.
    """
    even = n % 2 == 0
    up = (46 if even else 64) + 28
    lane = 128 - 3 + up * 2 ** ((n - 6) // 2 if even else (n - 7) // 2)
    worst: int = max(lane, _INDEXED.get(n, 0))
    return worst


def _dig(n: int, p: str) -> int:
    """The R by C grid at a byte a cell, its two coordinates, two counters."""
    bl = int.bit_length
    lines = p.split("\n")
    rows, cols = len(lines), max(map(len, lines))
    return 8 * rows * cols + bl(rows - 1) + bl(cols - 1) + bl(2 * n - 1) + bl(n) + 10


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    return _dig(n, p)
