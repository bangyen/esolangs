"""Back's emitted characters: the load column, or one row a tree node."""


def _chars(n: int, _: str) -> int:
    """N = max(18n^2 + 27n - 4, 9T + 18n^2 - 18n + 1); the first is exact to n = 4."""
    return max(18 * n * n + 27 * n - 4, 9 * (1 << n) + 18 * n * n - 18 * n + 1)


FORMULAS = {"scaling": (_chars, False, (3, 4, 5, 6))}
