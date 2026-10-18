"""Executed command bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    return min(12 * n + 69, 10 * n + 99)
