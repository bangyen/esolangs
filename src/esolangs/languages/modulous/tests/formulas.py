"""Modulous's emitted characters: the literal and one weighted read an input."""


def _chars(n: int, _: str) -> int:
    """Worst source: direct tails through four, otherwise the old envelope minus28."""
    if n == 1:
        return 68
    if n <= 4:
        return 6 * (1 << n) + 28 * n + 21
    return (1 << n) + 54 + 48 * n + sum(len(str(1 << k)) for k in range(n))


FORMULAS = {"scaling": (_chars, True, (3, 4, 5, 8))}
