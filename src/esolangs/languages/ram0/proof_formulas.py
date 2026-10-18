"""Snapshot-bit bounds."""


def _floor1(x: int) -> int:
    """Bits of a non-negative int: zero still costs one."""
    return max(1, int.bit_length(x))


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    return n + bl(len(p.split())) + 2 * _floor1(n - 1) + sum(map(_floor1, range(n)))
