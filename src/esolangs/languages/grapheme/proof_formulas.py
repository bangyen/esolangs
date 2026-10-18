"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    return 14 * n + 32 + len(str(2**2**n))


def _grapheme(n: int, _: str) -> int:
    """The call frame's program text, ``d`` the digit count of 2^T."""
    bl = int.bit_length
    t = 2**n
    d = len(str(2**t))
    lifted = bl(10 ** (d + 1) + 2**t - 1)
    return 16 * d + 112 * n + 312 + bl(14 * n + d + 17) + 2 * lifted + bl(2 * n) + bl(n)


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    return _grapheme(n, p)
