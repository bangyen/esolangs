"""LaserFuck's emitted area in cells: the tree, then the three-row lookup."""


def _cells(n: int, _: str) -> int:
    """N = max(T, 3)(13n + 32) to n = 6, then 3(18T + 52n + 5).

    The tree's worst is parity ending on a one: every node distinct.
    """
    if n <= 6:
        return max(1 << n, 3) * (13 * n + 32)
    return 3 * (18 * (1 << n) + 52 * n + 5)


FORMULAS = {"scaling": (_cells, True, (1, 2, 3, 4, 5, 6, 7, 8))}
