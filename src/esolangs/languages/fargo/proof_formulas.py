"""Executed command bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    if n > 5:
        return 5 * (1 << n) + 1
    return 15 * (1 << n) // 2 - 4
