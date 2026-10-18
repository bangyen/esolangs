"""Snapshot-bit bounds."""


def _floor1(x: int) -> int:
    """Bits of a non-negative int: zero still costs one."""
    return max(1, int.bit_length(x))


def workspace(n: int, _: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    return (
        n
        + 1
        + bl(3 * n - 2)
        + bl(n - 1)
        + bl(2 * n - 1)
        + sum(_floor1(c) + 1 for c in range(n))
    )
