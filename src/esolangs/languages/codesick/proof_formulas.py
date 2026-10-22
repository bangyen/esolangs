"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """The input as key, the unread bits and a marker, the last line's ip.

    The root has the largest id, at most C + 1, C the most nonconstant nodes.
    """
    c = sum(min(1 << d, (1 << (1 << (n - d))) - 2) for d in range(n))
    return 16 * n + 8 + 8 * len(str(c + 1)) + (3 * c + 1).bit_length()
