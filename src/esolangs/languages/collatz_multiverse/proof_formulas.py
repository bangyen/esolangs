"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    return (1 << n) // 4 + 3 * n + 130


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    return (
        -(-(1 << n) // 4) * (bl(len(p) // 17) + 6)
        + 64 * (bl(len(p) // 17) + 1)
        + (n * n + 168) * (8 * n + bl(len(p)) + 9) // 2
        + 2 * bl(len(p))
        + 115
    )
