"""B-tapemark's emitted cells and executed steps: the least-area layout."""

from math import isqrt


def _narrow(n: int, m: int | None = None) -> tuple[int, int, int]:
    """(characters, widest row, rows) of the narrow staircase, m essential inputs."""
    t = 1 << (n if m is None else m)
    return 16 * t + 54 * n + 14, t // 2 + 7, 2 * t + 7 * n + 3


def _wide(n: int, m: int | None = None) -> tuple[int, int, int]:
    """(characters, widest row, rows) of the wide layout, m essential inputs."""
    t = 1 << (n if m is None else m)
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


def _weights(n: int, m: int) -> list[int]:
    """Stage weights: m essential inputs by place value, then n - m ignored."""
    return [1 << (m - 1 - i) for i in range(m)] + [0] * (n - m)


def _fold(n: int, c: int, r: int, m: int | None = None) -> tuple[int, int, int]:
    """(characters, widest row, rows) of T/c strips of c entries, runs of r.

    ``m`` essential inputs weigh 2^(m-1-i); the other n - m weigh 0.
    """
    m = n if m is None else m
    t = 1 << m
    strips = -(-t // c)
    chars = (2 * n + 1) * (n + 3) + (2 * strips - 1) * (3 * c + n + 5) + (n + 2)
    rows = (2 * n + 1) + (2 * strips - 1) + 1
    width = max(3 * c + n + 5, n + 3)
    for w in _weights(n, m):
        folds = -(-w // r) or 1
        x, k = (
            (41 + 2 * w, 7) if folds == 1 else (11 + 18 * folds + 2 * w, 2 * folds + 3)
        )
        chars += x + k * (n + 3)
        rows += k
        width = max(width, n + 12 + min(w, r))
    return chars + rows - 1, width, rows


def _candidates(n: int, m: int) -> list[tuple[str, int, int, tuple[int, int, int]]]:
    """Shipped candidates in order: wide, narrow, then the closed-form folds."""
    t = 1 << n
    out = [("wide", 0, 0, _wide(n, m)), ("narrow", 0, 0, _narrow(n, m))]
    half = 18 * n - 9
    best = (half + isqrt(half * half + 48 * t)) // 6
    for c in dict.fromkeys([best, best * 17 // 20]):
        for r in dict.fromkeys([max(1, 3 * c - 12), t]):
            if c < 1 << m:
                out.append(("fold", c, r, _fold(n, c, r, m)))
    return out


def _cells(n: int, _: str) -> int:
    """A: cells (width x rows) of the least-area of wide, narrow and four folds."""
    return min(w * h for *_, (_, w, h) in _candidates(n, n))


def _steps_for(n: int, m: int) -> int:
    """Commands of the all-zero row when m of n inputs are essential.

    The shipped layout is the least (area, characters) candidate, a function
    of n and m alone.  Its row 0 is longest: a stage's one-side is shorter
    than the zero-side walk of its weight, two commands a cell.  Wide
    4T + 42n + 5, narrow 15T + 37n - 4m + 11 (T = 2^m); a fold of S strips
    of c entries with runs of r is T + 6Sc + 8S - 3c + 44n - 2, plus 4f - 6
    for each stage whose weight breaks into f >= 2 runs.
    """
    t = 1 << m
    name, c, r, _ = min(_candidates(n, m), key=lambda k: (k[3][1] * k[3][2], k[3][0]))
    if name == "wide":
        return 4 * t + 42 * n + 5
    if name == "narrow":
        return 15 * t + 37 * n - 4 * m + 11
    strips = -(-t // c)
    runs = (-(-w // r) for w in _weights(n, m))
    return (
        t
        + 6 * strips * c
        + 8 * strips
        - 3 * c
        + 44 * n
        - 2
        + sum(4 * f - 6 for f in runs if f >= 2)
    )


def _steps(n: int, _: str) -> int:
    """E: the longest all-zero row over the essential counts m (T > n entries).

    Fewer essential inputs mean fewer table entries but a stage each for the
    ignored ones, so m = n - 1 beats m = n at n = 7 (1,206 against 1,201).
    """
    return max(_steps_for(n, m) for m in range(1, n + 1) if 1 << m > n)


FORMULAS = {
    "scaling": (_cells, True, (3, 4, 5, 6, 7, 8)),
    "execution": (_steps, True, (3, 4, 5, 6, 7, 8)),
}
