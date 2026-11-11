"""BFStack's emitted characters: one byte-indexed block, then a tree of blocks.

Workspace is exact at n = 5 and from n = 9 (elsewhere the root loop cannot clear L/2).
"""


def witness(n: int) -> str:
    """Workspace witness, n = 5: one row at ``T / 2``, zeros elsewhere.

    Its cascade lists ``T - 1`` rows from 3 + 54n + T - 1 >= 256 with L < 512,
    so each open loop costs ``bl(L)``; n = 5 measures 321 on it.
    """
    t = 1 << n
    return "0" * (t // 2) + "1" + "0" * (t // 2 - 1)
