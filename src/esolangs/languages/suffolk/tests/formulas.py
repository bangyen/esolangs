"""Suffolk's emitted characters: the countdown sweep."""


def _chars(n: int, _: str) -> int:
    """F: L* - [n >= 7] for n <= 12, then the bound F - 1 = L* - 2 (L* below).

    L* = (17T + 316n + 482)/2.  The sweep is a constant plus a cost per half,
    strictly rising in the half's step count, and two fully alternating halves
    are equal (the top input ignored), so no table exceeds L*.  Tables at L*
    (one half alternating, the other one pair short) have at most n + 1 DAG
    nodes and the DAG wins from n = 7; those at L* - 1 (both halves one pair
    short) have at most 2n - 1, which the node limit (3n - 14 for large n)
    stops admitting at n = 13, so L* - 1 is reached for n = 7..12 only and
    F - 1 bounds n >= 13.
    """
    return (17 * (1 << n) + 316 * n + 482) // 2 - (n >= 7) - (n >= 13)


FORMULAS = {"scaling": (_chars, True, (4, 5, 6, 7, 8, 9, 10, 11, 12))}
