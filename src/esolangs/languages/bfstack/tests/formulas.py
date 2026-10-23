"""BFStack's emitted characters: one byte-indexed block, then a tree of blocks.

Workspace is exact at n = 5 and from n = 9 (elsewhere the root loop cannot clear L/2).
"""

from esolangs.languages.bfstack.proof_formulas import workspace


def _chars(n: int, _: str) -> int:
    """N = 3T + 54n + 59 through n = 7, then 221T/32 - 62 (62 a split, 822 a block)."""
    t = 1 << n
    return 3 * t + 54 * n + 59 if n <= 7 else 221 * t // 32 - 62


def witness(n: int) -> str:
    """Workspace witness, n = 5: a zero run of ``(3T + 1) // 5`` rows, then ones.

    Its cascade starts at 3 + 54n + T - 1 >= 256 with L < 512, so each open loop
    costs ``bl(L)``; n = 5 measures 213 here and on no other zero/one split.
    """
    t = 1 << n
    z = (3 * t + 1) // 5
    return "0" * z + "1" * (t - z)


FORMULAS = {
    "scaling": (_chars, True, (3, 4, 5, 6, 7, 8, 9)),
    "workspace": (workspace, frozenset({5, 9, 10, 11}), (3, 5, 6, 9, 10, 11)),
}
