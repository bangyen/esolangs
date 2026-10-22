"""ArrowQueue's emitted cells: the least-area of the cascade and its folds."""

from math import isqrt


def _fold(n: int, height: int, leaves: int) -> int | None:
    """Cells of the fold at ``height``: blocks packed greedily into strips.

    Blocks are n stages (6 lines, 5 wide), the middle (7, 4, shifts its
    strip one right unless last), ``leaves`` one-line leaves and the 2-line
    end block (6 wide).  ``None`` when one strip holds everything.
    """
    cap = height - 3
    blocks = [(6, 5, 0)] * n + [(7, 4, 1)] + [(1, 6, 0)] * leaves + [(2, 6, 0)]
    strips = [[0, 0, 0]]
    for lines, width, middle in blocks:
        if strips[-1][0] + lines > cap:
            strips.append([0, 0, 0])
        strip = strips[-1]
        strip[0] += lines
        strip[1] = max(strip[1], width)
        strip[2] |= middle
    if len(strips) == 1:
        return None
    last = len(strips) - 1
    wide = sum(s[1] + (i < last and s[2]) for i, s in enumerate(strips))
    return wide * max(2 + s[0] + (i < last) for i, s in enumerate(strips))


def _cells(n: int, _: str) -> int:
    """A: the least of the 6-wide cascade and the four folds, T - 1 leaves.

    A fold's area never falls as leaves are added, so T - 1 bounds every
    table.  A ones-then-zero-last table reaches it from n = 4 (its leaf
    order is permutation-invariant); the lone zero second to last, n <= 3.
    """
    t = 1 << n
    centre = (3 + isqrt(9 + 12 * (6 * n + 7 + t))) // 2
    folds = (_fold(n, max(10, h), t - 1) for h in range(centre - 1, centre + 3))
    return min(6 * (2 * t + 6 * n + 7), *(f for f in folds if f is not None))


FORMULAS = {"scaling": (_cells, True, (3, 4, 5, 6, 7, 8))}
