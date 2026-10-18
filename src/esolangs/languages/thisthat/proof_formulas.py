"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    if n % 2 == 0:
        return 32 * (1 << (n // 2)) - 29
    return 48 * (1 << ((n - 1) // 2)) - 29


def _floor1(x: int) -> int:
    """Bits of a non-negative int: zero still costs one."""
    return max(1, int.bit_length(x))


def workspace(n: int, _: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    return 4 * n + 89 + 2 * bl(n) + sum(map(_floor1, range(n)))
