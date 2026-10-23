"""Piet's emitted codels: the strip, or the packed fold's plan, whichever is smaller."""

from math import isqrt


def _strip(n: int) -> int:
    """Three rows by the lookup's blocks: 2m + z + 3k + 2n + 15 codels, +3 wide.

    Worst at k = n essential inputs and z = T - 2 zero entries (more is a
    literal product): 3 * (3T + 5n + 16).
    """
    return 3 * (3 * (1 << n) + 5 * n + 16)


def _fold(blocks: int) -> int:
    """The fold plan's area bound for ``blocks`` codels of bounded operations.

    Columns c = max(13, isqrt(2C - 1) + 9).  A row packs at least c - 9
    codels (room is c - 7 or less, a block wastes one), so R <= 1 +
    (C - 1) // (c - 9) rows; a right/left row pair is five rows tall, the
    last bend two more, plus the border: height <= 5R/2 + 3, width <= c.
    """
    columns = max(13, isqrt(2 * blocks - 1) + 9)
    rows = 1 + (blocks - 1) // (columns - 9)
    return columns * (5 * rows // 2 + 3 + 1)


def _codels(n: int, _: str) -> int:
    """F: min(strip, fold) at the most blocks C = 2T + 8n + 17 a table has."""
    return min(_strip(n), max(_fold(c) for c in range(2, 2 * (1 << n) + 8 * n + 18)))


FORMULAS = {"scaling": (_codels, False, (3, 4, 5, 6, 7, 8))}
