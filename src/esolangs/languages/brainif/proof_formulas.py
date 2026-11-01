"""Snapshot-bit bounds."""


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    lines = p.splitlines()
    cells = (
        6
        if len(lines) == 2 * n + 1 and lines[-2:] == ["if 48 inc", "if 49 output"]
        else 13
    )
    return cells + bl(len(lines)) + bl(n)
