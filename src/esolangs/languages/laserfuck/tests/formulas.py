"""LaserFuck's emitted area in cells: the tree, then the three-row lookup."""


def _cells(n: int, _: str) -> int:
    """N = max(T, 3)(12n + 32) to n = 6, then 3(11T + 52n + 3).

    The tree's worst is parity ending on a one: every node distinct.
    """
    if n <= 6:
        return max(1 << n, 3) * (12 * n + 32)
    return 3 * (11 * (1 << n) + 52 * n + 3)
