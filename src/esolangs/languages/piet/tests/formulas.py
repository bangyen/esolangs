"""Piet's emitted codels: the strip, or the least-area packed layout.

To n = 7 every packed layout is a function of the operations' block sizes alone
(a lane takes whole blocks to its room; 5,800 random tables at n = 5..7 never
cost a clash row), and a table with n essential inputs, z zeros and neither half
constant has the sizes ``[1] * (T + z)`` then a tail that depends on n only.
So the shipped area is a function of (n, z): the worst is its maximum over z.
From n = 8 a colour clash can cost a row (+32 codels at n = 8, in 53 of 1,277
tables), the rows depend on the bit pattern, and only the fold's bound holds.
"""

from math import isqrt


def _tail(n: int) -> list[int]:
    """Block sizes after the T + z entries: row number, select, print, halt pad."""
    return [
        *(1, 1),  # push 1, not
        *(2, 1, 1, 1) * n,  # per input: push 2, multiply, in, add
        1,  # push T, rebuilt by doubling:
        *(2, 1) * n,  # push 2, multiply
        *(2, 1, 1, 1, 1, 1, 2, 1, 1, 1),  # the roll
        1,  # print
        *(2, 1),  # push 2, pop keep the halt off the last turn
    ]


def _lanes(entries: int, tail: list[int], columns: int, kind: int) -> tuple[int, int]:
    """Width and lane count of the greedy plan; kind 0 plain, 1 shared, 2 short."""
    total = entries + len(tail)
    at, x, direction, widest, count = 0, 2, 1, 1, 0
    while at < total:
        room = columns - x - 4 if direction == 1 else x - (9 if kind == 0 else 7)
        used = max(0, min(entries - at, room))
        at += used
        while entries <= at < total:
            size = tail[at - entries]
            if used + (3 if at == total - 2 else size) > room:
                break
            used += size
            at += 1
        assert used, "no room for a block"
        end = x + direction * used
        widest = max(widest, end + 3 if direction == 1 and at < total else x, end)
        x = (end + 1 if direction == 1 else end - 2) if kind == 2 else end - direction
        direction, count = -direction, count + 1
    return widest + 1, count


def _packed(n: int, z: int) -> int:
    """The least area of the nine layouts: width * (rows + 4), or 2 * rows + 2 plain."""
    tail, entries = _tail(n), (1 << n) + z
    root = isqrt(entries + sum(tail))
    best = None
    for kind, floor in ((0, 22), (1, 18), (2, 18)):
        for offset in (5, 9, 13):
            width, lanes = _lanes(entries, tail, max(floor, root + offset), kind)
            rows = 3 if lanes == 1 else lanes + 4 if kind else 2 * lanes + 2
            best = width * rows if best is None else min(best, width * rows)
    assert best is not None
    return best


def _strip(n: int, z: int) -> int:
    """Three rows by 2T + z + 5n + 18 columns."""
    return 3 * (2 * (1 << n) + z + 5 * n + 18)


def zeros(n: int) -> int:
    """The last z whose shipped area is the worst."""
    shipped = {z: min(_strip(n, z), _packed(n, z)) for z in range(2, (1 << n) - 1)}
    return max(shipped, key=lambda z: (shipped[z], z))


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
    """F: max over z in [2, T - 2] of min(strip, least packed layout) to n = 7.

    Fewer essential inputs or a constant half store fewer entries (the family
    scan never reached the plain family).  From n = 8 the result is also at
    most the fold, drawn in the race, at the most blocks C = 2T + 8n + 17.
    """
    if n >= 8:
        return min(
            3 * (3 * (1 << n) + 5 * n + 16),
            max(_fold(c) for c in range(2, 2 * (1 << n) + 8 * n + 18)),
        )
    z = zeros(n)
    return min(_strip(n, z), _packed(n, z))


FORMULAS = {"scaling": (_codels, frozenset(range(3, 8)), (3, 4, 5, 6, 7, 8))}
