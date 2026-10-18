"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    if n <= 7:
        return 19 * (1 << n) // 2 - n - 4
    return 3 * (1 << n) // 64 + 1206 - n


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    return (
        min(1 << n, 128)
        + 2 * n
        + min(n, 7)
        + 192
        + 16 * (n > 7)
        + bl(len(p))
        + 2 * bl(n)
    )
