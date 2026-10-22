"""Alight's emitted characters: the straight lookup, every input essential."""


def _chars(n: int, _: str) -> int:
    """T + 16n + 38 + the digits of 48(T-1), the offset the index subtracts."""
    return (1 << n) + 16 * n + 38 + len(str(48 * ((1 << n) - 1)))


FORMULAS = {"scaling": (_chars, True, (3, 4, 5))}
