"""Executed command bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program.

    Commands = 7 + expanded tokens + 2 per executed shared-name reference
    (reference token and frame finish).  A block of size s >= 2 costs at most
    4 + 2c(s/2) tokens with its four references named, so c(s) <= 9s - 12.
    """
    return 9 * (1 << n) - 5


def workspace(_n: int, program: str) -> int:
    """The false literal writes 18 bits; other forms retain the frame bound."""
    # `$` writes a 17-bit output frame and a 1-bit instruction cursor.
    # Input number and input cursor stay read-only; n=1,3,6,8,12 executed.
    if program == "$":
        return 18
    length = len(program)
    return 16 * (length - 3) + length.bit_length() + 11
