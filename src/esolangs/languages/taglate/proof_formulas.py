"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """Even n past 2, then odd n through a ghost input, m = n + 1."""
    if n % 2 == 0:
        return 16 * (1 << n) + (7 * n * n + 26 * n - 22) // 2
    m = n + 1
    return 28 * (1 << n) + (7 * m * m + 22 * m - 36) // 2


def workspace(n: int, p: str) -> int:
    """Six-bit queue cells; odd n gets a ghost input, m even."""
    m = 2 * -(-n // 2)
    return (
        24 * (1 << m)
        + 12 * m
        + 12
        + int.bit_length(m)
        + int.bit_length(len(p) - 4 * (1 << m) - 7 * m + 1)
    )
