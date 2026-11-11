"""Uncontracted command bounds."""


def execution(n: int, p: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    if "◧" not in p and p.count("□") + p.count("■") == 1 and p.count("◇") == n + 1:
        return 2 * n + 5
    if n % 2 == 0:
        return 32 * (1 << (n // 2)) - 29
    return 48 * (1 << ((n - 1) // 2)) - 29
