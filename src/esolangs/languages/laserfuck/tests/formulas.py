"""LaserFuck's emitted characters: the tree, then the three-row lookup."""


def _chars(n: int, _: str) -> int:
    """N = T(25n + 65)/2 - 1 to n = 6, parity; then 24T + 104n + 11, one zero."""
    if n <= 6:
        return (25 * n + 65) * (1 << n) // 2 - 1
    return 24 * (1 << n) + 104 * n + 11


FORMULAS = {"scaling": (_chars, True, (3, 4, 5, 6, 7, 8))}
