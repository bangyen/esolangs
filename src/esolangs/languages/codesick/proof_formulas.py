"""Snapshot-bit bounds."""


def node_count(n: int) -> int:
    """Sum the level caps, deciding a losing tower on its exponent."""
    total = 0
    for depth in range(n):
        remaining = n - depth
        fits = (remaining == 1 and depth >= 1) or remaining < depth.bit_length()
        total += (1 << (1 << remaining)) - 2 if fits else 1 << depth
    return total


def workspace(n: int, _: str) -> int:
    """The input as key, the unread bits and a marker, the last line's ip.

    A marker has at most digits10(C+1) ASCII characters: base88 names
    skip three keywords, and C bounds the nonconstant node count.
    """
    c = node_count(n)
    return 16 * n + 8 + 8 * len(str(c + 1)) + (3 * c + 1).bit_length()
