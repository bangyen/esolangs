"""Back's emitted characters: the load column, or one row a tree node."""


def _chars(n: int, _: str) -> int:
    """C: all rows load-width to n = 5; past it the tree rows above the load.

    Rows: 6n - 1 of load (width 3n + 4, two rows 1 wider); the Rudin-Shapiro
    witness shares nothing, so its 3T/4 one-edge rows run in order, triples
    (8, 5, 11 + 3v2(j)) with v2 the 2-adic valuation, a row for a level-k node
    3(n - k) + 2 characters.  The first T/4 - 2n triples show above the load:
    s = popcount(T/4 - 2n), the sum of v2 being m - s.
    """
    if n <= 5:
        return 18 * n * n + 27 * n - 4
    t = 1 << n
    return 18 * n * n - 30 * n + 10 + 15 * t // 2 - 3 * (t // 4 - 2 * n).bit_count()


FORMULAS = {"scaling": (_chars, True, (3, 4, 5, 6, 7, 8))}
