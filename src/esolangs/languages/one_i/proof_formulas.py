"""Snapshot-bit bounds."""


def workspace(n: int, program: str) -> int:
    """Two literal offsets and a frame, n + 4 bits each, at n = 6..13.

    From n = 14 a constant's frame pc takes five bits; there the bound is
    4bl(L) + 40.
    """
    bl = int.bit_length
    if 6 <= n <= 13:
        return 3 * n + 52 + bl(2 * n - 1)
    return 4 * bl(len(program)) + 40
