"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """Commands: one closed form past 2."""
    return 10 * (1 << n) + 4 * n * n + 11 * n + 14


def workspace(n: int, p: str) -> int:
    """Six-bit queue cells at the end of the read, plus cursor and input count."""
    return (
        24 * (1 << n)
        + 18 * n
        + 12
        + int.bit_length(n)
        + int.bit_length(len(p) - 4 * (1 << n) - 6 * n - 5)
    )
