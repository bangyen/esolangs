"""Snapshot-bit bounds."""


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    return (
        bl(len(p) - 1)
        + max(12, bl(2 * n - 2) + 10)
        + n
        + sum(map(bl, range(1, n)))
        + bl(2 * n)
        + bl(n)
    )
