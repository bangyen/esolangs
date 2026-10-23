"""B-tapemark's cells, steps and written bits: the least-area layout."""

from math import isqrt

from esolangs.languages.b_tapemark.proof_formulas import workspace

_STAGE = (
    "|/    \\",
    "*\\-|\\ 0",
    "\\   | |",
    "\\|*%/ \\|\\",
    "    /",
    "/   /*  /",
    "|",
)
_NARROW_STAGE = (
    "|/   \\",
    "*\\-|\\0",
    "\\   ||",
    "\\|*%/\\|\\",
    "    /",
    "/   /* /",
    "|",
)
_STEP = ((1, 0), (0, 1), (-1, 0), (0, -1))
_MIRROR = {"\\": (1, 0, 3, 2), "/": (3, 2, 1, 0)}


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


def _bits(v: int) -> int:
    """Bits the snapshot counts for an int: its length (1 for 0), 1 more if negative."""
    return (v.bit_length() or 1) + (v < 0)


def _mark(x: int, y: int) -> int:
    """A cell of either grid: its character and its two coordinates."""
    return 8 + _bits(x) + _bits(y)


def _program(
    n: int, name: str, c: int, r: int
) -> tuple[dict[tuple[int, int], str], list[tuple[int, int]]]:
    """Rendered cells of the shipped layout, m = n, and each stage's origin.

    The start marker is a cell here (it fixes the render); the stage origins
    are where the beam enters a stage heading down.
    """
    cells: dict[tuple[int, int], str] = {}
    stages: list[tuple[int, int]] = []

    def put(x: int, y: int, text: str) -> None:
        for i, char in enumerate(text):
            if char != " ":
                cells[x + i, y] = char

    t = 1 << n
    narrow = name == "narrow"
    # Copy: the beam runs west over t triples ``|d*``, the start on its east end.
    if narrow:
        for i in range(t):
            put(2, 2 * i, "|0*")
            put(1, 2 * i, "/")
            put(5, 2 * i, "<" if i == 0 else "/")
            if i + 1 < t:
                put(1, 2 * i + 1, "\\")
                put(5, 2 * i + 1, "\\")
        bottom = 2 * t - 1
        put(1, bottom, "\\")
        put(6, bottom, "/")
        for k in range(1, 2 * n + 1):
            put(6, bottom - k, "|")
        put(6, -1, "\\")
        put(0, -1, "/")
        top = bottom + 1
    else:
        width = c or t
        east = 3 * width + (2 if c else 1)
        for i in range(t):
            put(east - 3 - 3 * (i % width), 2 * (i // width), "|0*")
        put(east, 0, "<")
        strips = -(-t // width)
        for k in range(strips - 1):
            put(1, 2 * k, "/")
            put(1, 2 * k + 1, "\\")
            put(east, 2 * k + 1, "\\")
            put(east, 2 * k + 2, "/")
        last = 2 * (strips - 1)
        put(0, last, "\\")
        for k in range(1, 2 * n + 1):
            put(0, -k, "|")
        put(0, -2 * n - 1, "\\")
        put(-1, -2 * n - 1, "/")
        top = last + 1
    for i in range(n):
        w = 1 << (n - 1 - i)
        stages.append((0 if narrow else -1, top))
        if narrow:
            for k, line in enumerate(_NARROW_STAGE):
                put(0, top + k, line)
            run, extra, turn = max(6, 8 - w), 0, [w]
        else:
            turn = [r] * (w // r) + ([w % r] if w % r else []) if c else [w]
            extra = max(0, 2 * len(turn) - 4)
            for k, line in enumerate(_STAGE):
                put(-1, top + k + (extra if k >= 4 else 0), line)
            run = 9 if c else 8
        for k, length in enumerate(turn):
            y = top + 1 + 2 * k
            put(run, y, "|" * length + "\\")
            if k + 1 < len(turn):
                put(run + length, y + 1, "/")
                put(run - 1, y + 1, "/")
                put(run - 1, y + 2, "\\")
            else:
                put(run + length, top + 4 + extra, "/")
        top += 7 + extra
    if narrow:
        put(0, top, "\\")
        put(n + 1, top, "\\")
        put(n + 1, top + 1, "/")
        put(0, top + 1, "!+" + "|" * (n - 1))
    else:
        put(-1, top, "/")
        put(-n - 1, top, "+" + "|" * (n - 1))
        put(-n - 2, top, "!")
    # Render: wholly blank rows and columns go.
    xs = {x: i for i, x in enumerate(sorted({x for x, _ in cells}))}
    ys = {y: i for i, y in enumerate(sorted({y for _, y in cells}))}
    return (
        {(xs[x], ys[y]): char for (x, y), char in cells.items()},
        [(xs[x], ys[y]) for x, y in stages],
    )


def _tail(
    cells: dict[tuple[int, int], str],
    data: dict[tuple[int, int], str],
    at: tuple[int, int],
    pointer: tuple[int, int],
    digit: str,
) -> int:
    """Most bits of marks written and positions on the last stage's way out.

    The beam enters the stage at ``at`` heading down with the mark pointer
    at ``pointer``; ``digit`` is the input it reads.  The commands are the
    interpreter's: ``|`` steps the data pointer, ``*`` copies the cell it
    skips onto a blank data cell, ``-`` reads into one, a digit heading
    vertically swaps grids when the data cell equals it, ``%`` swaps on a
    mark, ``!`` halts.
    """
    grids = [cells, data]
    where = [at, pointer]
    swapped, heading, written, peak = 0, 1, 0, 0
    pending = [digit]
    while (cmd := grids[swapped].get(where[swapped], " ")) != "!":
        other = 1 - swapped
        under = grids[other].get(where[other], " ")
        if cmd in _MIRROR:
            heading = _MIRROR[cmd][heading]
        elif cmd == "-" and under == " ":
            grids[other][where[other]] = pending.pop()
            written += _mark(*where[other])
        elif cmd == "*":
            x, y = where[swapped]
            where[swapped] = x + _STEP[heading][0], y + _STEP[heading][1]
            skipped = grids[swapped].get(where[swapped], " ")
            if under == " " and skipped != " ":
                grids[other][where[other]] = skipped
                written += _mark(*where[other])
        elif cmd == "|":
            x, y = where[other]
            where[other] = x + _STEP[heading][0], y + _STEP[heading][1]
        elif (cmd == "%" and under != " ") or (
            cmd.isdigit() and heading % 2 == 1 and under == cmd
        ):
            swapped = other
        x, y = where[swapped]
        where[swapped] = x + _STEP[heading][0], y + _STEP[heading][1]
        peak = max(
            peak,
            written
            + sum(_bits(v) for p in where for v in p)
            + _bits(swapped)
            + _bits(heading)
            + 1,
        )
    return peak


def _model_workspace(n: int) -> int:
    """W: the largest snapshot, all n inputs essential, over every row.

    A snapshot counts the program's cells (8 + both coordinates, the start
    marker apart), the data grid's marks the same way, both pointers, the swap,
    the heading and the halted flag, and bl(n) for the input consumed.  The
    layout is a function of n alone and never reads a table digit, so any
    table with every input essential reaches W.  The marks are the table's T
    at (x0 - k, y0), then for stage s, y = y0 - 2n + 2s: the input at (x, y)
    and the pair ``\\`` ``%`` at (x, y + 1), (x + 1, y + 1), with x = x0 - T + s
    plus the weights of the zero bits before s.  Both steps below are exhaustive
    on the shipped generator and interpreter, every essential set and every row
    (n = 3..8; a table's digits move no cell and no beam, so the set fixes the
    run: 3 random tables per set agree row for row, n <= 5), the snapshot counted
    as ``WrittenState`` does.  The peak falls in the last stage's walk to ``!``,
    at least 29 bits above every earlier snapshot, so earlier stages sum in
    closed form and ``_tail`` walks the last.  An ignored input only shrinks the
    table: the largest peak over sets of m < n essential inputs (n = 3..8: 2,034,
    3,167, 4,943, 8,062, 13,951, 17,639; constant tables at most 334) stays below W
    (2,615, 4,363, 7,469, 9,652, 16,590, 30,563).
    """
    t = 1 << n
    name, c, r, _ = min(_candidates(n, n), key=lambda k: (k[3][1] * k[3][2], k[3][0]))
    cells, stages = _program(n, name, c, r)
    x0, y0 = next(k for k, v in cells.items() if v in "<>^v")
    del cells[x0, y0]
    table = {(x0 - k, y0): "0" for k in range(t)}
    base = sum(_mark(*p) for p in table)
    worst = 0
    for row in range(t):
        data, marks, x = dict(table), base, x0 - t
        for s in range(n - 1):
            y = y0 - 2 * n + 2 * s
            for p in ((x, y), (x, y + 1), (x + 1, y + 1)):
                data[p] = "0"
                marks += _mark(*p)
            x += 1 + (0 if row >> (n - 1 - s) & 1 else 1 << (n - 1 - s))
        last = (x, y0 - 2)
        worst = max(worst, marks + _tail(cells, data, stages[-1], last, str(row & 1)))
    return sum(_mark(*p) for p in cells) + worst + n.bit_length()


def _workspace(n: int, program: str) -> int:
    """W to n = 7; past it the program-cell bound B, which holds for every n."""
    return _model_workspace(n) if n <= 7 else workspace(n, program)


FORMULAS = {
    "scaling": (_cells, True, (3, 4, 5, 6, 7, 8)),
    "execution": (_steps, True, (3, 4, 5, 6, 7, 8)),
    "workspace": (_workspace, frozenset(range(3, 8)), (3, 4, 5, 6, 7)),
}
