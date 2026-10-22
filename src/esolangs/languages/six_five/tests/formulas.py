"""6-5's emitted characters: the shorter of two raced orders."""


def _chars(n: int, _: str) -> int:
    """N = max(6T + 17n + 3, tree route 6n + m(n + 13) + 4), m = min(35, T - 1).

    Past n = 35 the guarded walk gives 7T + 4n + 11.
    """
    t = 1 << n
    if n > 35:
        return 7 * t + 4 * n + 11  # guarded walk: every row's cell, one label
    m = min(35, t - 1)
    tree = 6 * n + m * (n + 13) + 4  # reads, m nodes of <= n + 8, m + 1 leaves of 5
    return max(6 * t + 17 * n + 3, tree)


FORMULAS = {"scaling": (_chars, False, (1, 2, 3, 4, 5, 6, 7, 8))}
