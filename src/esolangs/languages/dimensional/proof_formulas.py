"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    return (
        sum(map(bl, range(1 << n)))
        + 5 * (1 << n)
        + n * (n - 1) // 2
        + 4 * n
        + 6
        + bl(2 * (1 << n) + 20 * n + 56)
        + bl(2 * n - 1)
    )
