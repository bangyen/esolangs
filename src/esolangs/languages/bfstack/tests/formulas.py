"""BFStack's emitted characters: one byte-indexed block, then a tree of blocks."""


def _chars(n: int, _: str) -> int:
    """N = 3T + 54n + 59 through n = 7, then 221T/32 - 62 (62 a split, 822 a block)."""
    t = 1 << n
    return 3 * t + 54 * n + 59 if n <= 7 else 221 * t // 32 - 62


FORMULAS = {"scaling": (_chars, True, (3, 4, 5, 6, 7, 8, 9))}
