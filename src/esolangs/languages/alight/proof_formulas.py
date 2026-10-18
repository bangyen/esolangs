"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    return 72 * n + 762 + bl(6 * n + 12) + bl(n)
