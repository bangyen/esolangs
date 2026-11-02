"""Command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """Keep small trees within 5n; inline trees and folds within 3n+4."""
    return 5 * n if n <= 5 else 3 * n + 4


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
