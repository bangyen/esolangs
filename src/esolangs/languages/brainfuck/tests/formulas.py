"""Brainfuck's emitted characters: the plain tree, built on every table."""


def _chars(n: int, _: str) -> int:
    """35T/2 + 55n + 25: the plain tree on parity (n >= 1).

    Reads and the print are 49n + 2(n - 1) + 2(n - 1) + 2n + 49.  A test node is
    12 commands plus its arms; a leaf arm moves to the answer cell and back
    (4(n - i) for a 1, 4(n - i) - 1 under the zero side, nothing for a 0), so the
    longest tree tests every node with a 1-leaf at the bottom: 16 a bottom node,
    then 12 + 2 x (child + a 1- or 2-cell hop) a level up.  Folding equal halves
    only drops nodes; the shared-flag tree and the affine stream are conditional
    and never counted.  A recurrence over (level, flag the child leaves the
    pointer on) matches this closed form n = 1..16 and the plain tree exactly
    on every table n <= 4.
    """
    return 35 * 2**n // 2 + 55 * n + 25


FORMULAS = {"scaling": (_chars, False, (2, 3, 4, 5, 6, 7, 8))}
