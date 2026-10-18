"""Snapshot-bit bounds."""


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    return 13 + bl(len(p.splitlines())) + bl(n)
