"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """N - 1 forced thunks of 64 bits and their addresses, then the print block."""
    bl = int.bit_length
    return 64 * n + 306 + sum(map(bl, range(1, n))) + bl(n)
