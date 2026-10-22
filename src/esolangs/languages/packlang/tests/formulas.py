"""Packlang's emitted characters: one write per differing row, in blocks."""


def _d(x: int) -> int:
    return len(str(x))


def _top(rows: int, m: int, a: int) -> int:
    """Sum of (a + digits(r)) over the m largest rows r < rows."""
    total, r, left = 0, rows - 1, m
    while left > 0 and r >= 0:
        lo = 10 ** (_d(r) - 1) if r else 0
        take = min(left, r - lo + 1)
        total += take * (a + _d(r))
        left -= take
        r = lo - 1
    return total


def _block(rows: int) -> int:
    """Most characters of one block's writes.

    Singles (<= R/2 + 1) or a fill with punches (<= R/2 - 2).
    """
    single = _top(rows, rows // 2 + 1, 9)
    fill = 29 + _d(rows) + _top(rows, max(rows // 2 - 2, 0), 9)
    return max(single, fill)


def _chars(n: int, _: str) -> int:
    """N = headers + counters + per-block write bound + 3 a folded line."""
    low = min(n, 7)
    rows = 1 << low
    blocks = 1 << (n - low)
    # Package, i/d/c, q, array, main, closers.
    head = 15 + 30 + 10 + 18 + _d(rows) + 17 + 4 + 14
    if blocks > 1:
        head += 42 + 2 * _d(blocks - 1)  # block registers h, g
    counters = [31] + [64] * (low - 1)
    if blocks > 1:
        counters = [31] + [64] * (n - low - 1) + counters
    paint = 21 + sum(
        (13 + _d(b) + _block(rows) + 1) if blocks > 1 else _block(rows)
        for b in range(blocks)
    )
    lines = 1 + -(-(paint + 16 * blocks) // 56)
    return head + sum(counters) + paint + 3 * (len(counters) + lines)


FORMULAS = {"scaling": (_chars, False, (3, 4, 5, 6, 7, 8, 9, 10))}
