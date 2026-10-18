"""Executed command bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    return 8 * (1 << (2 * n)) + 43 * (1 << n) + 15 * n - 5
