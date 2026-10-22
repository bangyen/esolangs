"""Bitdeque's emitted characters: the shared tree, bounded by its token count."""


def _bound(n: int, _: str) -> int:
    """B: words of the program by distinct nonconstant subtrees c_d per level.

    S counts a general node and a zero-position pointer per unit; U = 4n + 25
    + 2S is the token bound and d the digits of its largest GOTO operand.
    """
    c = [min(1 << d, (1 << (1 << (n - d))) - 2) for d in range(n)]
    s = sum(c[d] + min(c[d], 2 * c[d] - c[d + 1]) for d in range(n - 1))
    u = 4 * n + 25 + 2 * s
    d = len(str(u + 1))
    # Prelude 8 words, n setters, two constant leaves, two last-level blocks,
    # then 13 + d characters a unit.
    return 34 + d + 12 * n + 8 * n + 46 + 2 * max(37, 23 + 2 * d) + (13 + d) * s - 1


FORMULAS = {"scaling": (_bound, False, (3, 4, 5, 6, 7))}
