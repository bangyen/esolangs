"""Snapshot-bit bounds."""


def _floor1(x: int) -> int:
    """Bits of a non-negative int: zero still costs one."""
    return max(1, int.bit_length(x))


def workspace(n: int, p: str) -> int:
    """Written bits; native constants change z, the cursor and the dump latch."""
    bl = int.bit_length
    if set(p.split()) <= {"Z", "A", "$"}:
        return 2 + bl(len(p.split()))
    return 1 + n + bl(len(p.split())) + 2 * _floor1(n - 1) + sum(map(_floor1, range(n)))
