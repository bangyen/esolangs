"""B-tapemark's emitted cells: the least-area layout."""

from math import isqrt


def _narrow(n: int) -> tuple[int, int, int]:
    """(characters, widest row, rows) of the narrow staircase."""
    t = 1 << n
    return 16 * t + 54 * n + 14, t // 2 + 7, 2 * t + 7 * n + 3


def _wide(n: int) -> tuple[int, int, int]:
    """(characters, widest row, rows) of the wide layout."""
    t = 1 << n
    rows = 9 * n + 3
    chars = (
        (2 * n + 1) * (n + 3)
        + (3 * t + n + 4)
        + 7 * n * (n + 3)
        + 39 * n
        + 2 * (t - 1)
        + (n + 2)
        + rows
        - 1
    )
    return chars, 3 * t + n + 4, rows


def _fold(n: int, c: int, r: int) -> tuple[int, int, int]:
    """(characters, widest row, rows) of T/c strips of c entries, runs of r."""
    t = 1 << n
    strips = -(-t // c)
    chars = (2 * n + 1) * (n + 3) + (2 * strips - 1) * (3 * c + n + 5) + (n + 2)
    rows = (2 * n + 1) + (2 * strips - 1) + 1
    width = max(3 * c + n + 5, n + 3)
    for i in range(n):
        w = 1 << (n - 1 - i)
        folds = -(-w // r)
        x, k = (
            (41 + 2 * w, 7) if folds == 1 else (11 + 18 * folds + 2 * w, 2 * folds + 3)
        )
        chars += x + k * (n + 3)
        rows += k
        width = max(width, n + 12 + min(w, r))
    return chars + rows - 1, width, rows


def _cells(n: int, _: str) -> int:
    """A: cells (width x rows) of the least-area of wide, narrow and four folds."""
    t = 1 << n
    candidates = [_wide(n), _narrow(n)]
    half = 18 * n - 9
    best = (half + isqrt(half * half + 48 * t)) // 6
    for c in dict.fromkeys([best, best * 17 // 20]):
        for r in dict.fromkeys([max(1, 3 * c - 12), t]):
            if c < t:
                candidates.append(_fold(n, c, r))
    return min(w * h for _, w, h in candidates)


FORMULAS = {"scaling": (_cells, True, (3, 4, 5, 6, 7, 8))}
