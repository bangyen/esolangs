"""Suffolk's emitted characters: the countdown sweep."""


def _chars(n: int, _: str) -> int:
    """L* - [n >= 7] for n <= 12, L* - 9 from n = 13 (L* below).

    L* = (17T + 316n + 482)/2.  The sweep is a constant plus a cost per half
    that depends only on the half's skipped rounds j (rounds without a step):
    floor(j/2) * (9 or 13) + (j odd), strictly rising in the steps, and two
    fully alternating halves are equal (the top input ignored), so no table
    exceeds L*.  Tables with j <= 2 in all have at most j(n - 2) + 3 DAG
    nodes: L* (one skip) and L* - 1 (one in each half) lose to the DAG from
    n = 7 and n = 13 (the node limit passes 2n - 1), and so does j0 = 2 at
    L* - 8.  The next sweeps (two skips in the first half, one in the second,
    or three in the first) have 3n - 5 nodes against a limit under 3n - 8 -
    bl(n), so they ship L* - 9, the worst.
    """
    return (17 * (1 << n) + 316 * n + 482) // 2 - (n >= 7) - 8 * (n >= 13)


FORMULAS = {"scaling": (_chars, True, (4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14))}
