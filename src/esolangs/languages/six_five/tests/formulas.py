"""6-5's emitted characters: the shorter of two raced orders."""


def _names(n: int) -> int:
    """Chars of a shared tree's distinct nodes: <= 7 + nav each, nav <= level."""
    total = 0
    for level in range(n):
        halves = 2 ** (2 ** (n - level)) - 2
        total += (1 if level == 0 else min(1 << level, level * halves)) * (
            7 + max(level, 1)
        )
    return total


def _chars(n: int, _: str) -> int:
    """N = max(6T + 17n + 3, tree route 6n + m(n + 13) + 4), m = min(35, T - 1).

    Past n = 35 the guarded walk gives 7T + 4n + 11.  Up to n = 5 the walk is
    never reached and the reverse order always builds both layouts: unshared
    11T + 6n - 9 (reads 6n - 2, 5 a node and a leaf, 1 a move) and shared
    6n + 22 + _names(n) (<= 4 leaf codes of 6, <= 27 labels); N is their min.
    """
    t = 1 << n
    if n > 35:
        return 7 * t + 4 * n + 11  # guarded walk: every row's cell, one label
    if n <= 5:
        return min(11 * t + 6 * n - 9, 6 * n + 22 + _names(n))
    m = min(35, t - 1)
    tree = 6 * n + m * (n + 13) + 4  # reads, m nodes of <= n + 8, m + 1 leaves of 5
    return max(6 * t + 17 * n + 3, tree)


FORMULAS = {"scaling": (_chars, False, (1, 2, 3, 4, 5, 6, 7, 8))}
