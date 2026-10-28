"""Executed command bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program.

    Commands = 7 + expanded tokens + 2 per executed shared-name reference
    (reference token and frame finish).  A block of size s >= 2 costs at most
    4 + 2c(s/2) tokens with its four references named, so c(s) <= 9s - 12.
    """
    return 9 * (1 << n) - 5
