"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """Commands: one closed form per parity of n past 2."""
    if n % 2 == 0:
        return 16 * (1 << n) + (7 * n * n + 26 * n - 22) // 2
    return 16 * (1 << n) + (7 * n * n + 36 * n + 5) // 2


def workspace(n: int, p: str) -> int:
    """Six-bit queue cells at the end of the read, plus cursor and input count."""
    if n % 2 == 0:
        return (
            24 * (1 << n)
            + 12 * n
            + 12
            + int.bit_length(n)
            + int.bit_length(len(p) - 4 * (1 << n) - 7 * n + 1)
        )
    return (
        24 * (1 << n)
        + 12 * n
        + 18
        + int.bit_length(n)
        + int.bit_length(len(p) - 4 * (1 << n) - 7 * n - 6)
    )
