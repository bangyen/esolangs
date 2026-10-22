"""Size bound for the per-node shortest of plain and carried subtrees."""


def scaling(n: int, _: str) -> int:
    """F: 161 at n = 4, then 7n + 31T/4 - 3: 7 a node over 5-input halves of <= 241.

    The plain composition is always a candidate, so a node is at most 7 plus
    its halves.  241 is the worst 5-input subtree: every ordered pair of
    4-input halves whose plain sum passes 234 was built (6.2M); 161 is the
    exhaustive n = 4 worst.
    """
    if n == 4:
        return 161
    return 7 * n + 31 * 2**n // 4 - 3


FORMULAS = {"scaling": (scaling, False, (4, 5, 6, 7))}
