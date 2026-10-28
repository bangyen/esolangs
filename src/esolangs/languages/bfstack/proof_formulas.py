"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program.

    A one arm costs 60 commands a wide level (a zero arm 59) over the worst
    seven-input block's 1,080: 3 + 51*7 + 4*7 + 127 encoding, 127 + 3*126 + 9
    over 126 zero rows, 50 printing, 1 closing ``<``.
    """
    return 60 * (n - 7) + 1080


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program.

    Past seven inputs the root is a zero arm (stack peak ``n + 6``) or a one
    arm (loop at position 51: six bits, not ``bl(L)``): never both at full
    width.  At n = 9 the zero arm's loop sits at most 2016 < 2^11 (a one arm
    of two 948-character blocks and a 62-character split), one bit short.
    """
    bl = int.bit_length
    return (
        n
        + 6
        + (n < 8)
        - (n == 9)
        + bl(n)
        + (max(n - 7, 0) + min(1 << n, 128) + 2) * bl(len(p))
    )
