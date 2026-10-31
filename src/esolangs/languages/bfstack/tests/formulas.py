"""BFStack's emitted characters: one byte-indexed block, then a tree of blocks.

Workspace is exact at n = 5 and from n = 9 (elsewhere the root loop cannot clear L/2).
"""

from esolangs.languages.bfstack.proof_formulas import workspace


def _chars(n: int, _: str) -> int:
    """N = 4T + 54n + 57 through n = 7, 1,509 at n = 8, then 393T/64 - 61.

    Past n = 8 a tree of 256-row blocks: one 1,511 (start 1, a one at row 0),
    the rest 1,510 (start 0, a one past row 1), 62 a split.  A block is the
    encoder's ``2 + 54*8 + 255``, a cascade over 254 zero rows ending at 255
    (``255 + 2*254 + 7``) and the printing 50.
    """
    t = 1 << n
    if n == 8:
        return 1509
    return 4 * t + 54 * n + 57 if n <= 7 else 393 * t // 64 - 61


def witness(n: int) -> str:
    """Workspace witness, n = 5: one row at ``T / 2``, zeros elsewhere.

    Its cascade lists ``T - 1`` rows from 3 + 54n + T - 1 >= 256 with L < 512,
    so each open loop costs ``bl(L)``; n = 5 measures 321 on it.
    """
    t = 1 << n
    return "0" * (t // 2) + "1" + "0" * (t // 2 - 1)


FORMULAS = {
    "scaling": (_chars, True, (3, 4, 5, 6, 7, 8, 9)),
    "workspace": (workspace, frozenset({5, 9, 10, 11}), (3, 5, 6, 9, 10, 11)),
}
