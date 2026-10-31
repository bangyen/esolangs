"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program.

    A one arm costs 60 commands a wide level (a zero arm 59) over the worst
    eight-input block's 1,769 commands, one more under a tree (the closing
    ``<``).
    """
    return 60 * (n - 8) + 1769 + (n > 8)


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program.

    Past seven inputs the root is a zero arm (stack peak ``n + 6``) or a one
    arm (loop at position 51: six bits, not ``bl(L)``): never both at full
    width.  At n = 9 the zero arm's loop sits below 2^11 (a one arm of a
    1,510-character block), one bit short.
    """
    bl = int.bit_length
    return (
        n
        + 6
        + (n < 8)
        - (n == 9)
        + bl(n)
        + (max(n - 8, 0) + min(1 << n, 255) + 2) * bl(len(p))
    )
