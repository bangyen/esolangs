"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """One command a character: 18 an input, a 17-letter frame, ``F…F``.

    The minimal lift has at most ``d + 1`` digits, ``d`` those of 2^T.
    """
    return 18 * n + 20 + len(str(2**2**n))


def _grapheme(n: int, _: str) -> int:
    """The call frame's program text, ``d`` the digit count of 2^T."""
    bl = int.bit_length
    t = 2**n
    d = len(str(2**t))
    return (
        16 * d
        + 144 * n
        + 208
        + bl(18 * n + d + 5)
        + 2 * bl(2 * 10**d)
        + bl(2 * n)
        + bl(n)
    )


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    return _grapheme(n, p)
