"""Snapshot-bit bounds."""


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    return (
        (7 * (1 << n) + 20 * n + 100) * (bl(len(p)) + 4)
        + sum(bl(j) + 2 for j in range((1 << n) // 2))
        + 2 * bl(len(p))
        + n
        + 2 * bl(n)
        + 32
    )
