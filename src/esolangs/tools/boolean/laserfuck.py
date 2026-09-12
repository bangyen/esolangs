r"""The LaserFuck boolean generator."""

from functools import cache
from itertools import permutations
from typing import NamedTuple

from esolangs.tools import laserfuck_layout
from esolangs.tools.boolean.helpers import (
    _ORDER_SEARCH_MAX,
    _validate_truth_table,
    permute_truth_table,
)

__all__ = ["laserfuck"]


# The two loops that normalize.
# ``'0'``/``'1'`` arrive as.
# Writing that straight costs.
# costs a counter instead, and.
# rather than by 48 ``+`` --.
_LASER_OUTER = 8
_LASER_INNER = 6


def _laserfuck_walk(frm: int, to: int) -> str:
    r"""Spell the tape walk from cell ``frm`` to cell ``to``."""
    return ">" * (to - frm) if to >= frm else "<" * (frm - to)


def _laserfuck_cells(n: int, perm: tuple[int, ...]) -> list[int]:
    r"""Return the cell each stream input is read into, indexed by input."""
    cells = [0] * n
    for level, i in enumerate(perm):
        cells[i] = level + 1
    return cells


def _laserfuck_reads(n: int, perm: tuple[int, ...]) -> str:
    r"""Spell the reader's read section, placing the inputs in ``perm``."""
    cells = _laserfuck_cells(n, perm)
    out = ""
    at = 1
    for cell in cells:
        out += _laserfuck_walk(at, cell) + ","
        at = cell
    return out + _laserfuck_walk(at, 0)


def _laserfuck_ring_reader(
    n: int, perm: tuple[int, ...] | None = None
) -> tuple[list[str], int]:
    r"""Build the looping input reader, and say how wide it is."""
    preload = ">" + "+" * _LASER_OUTER
    multiply = "<" + "+" * _LASER_INNER + ">" + "-#/)"
    # The reads land the inputs in.
    # Which input goes in which.
    reads = _laserfuck_reads(n, tuple(range(n)) if perm is None else perm)
    # one '-' for the counter and.
    retire = "".join("->" for _ in range(n)) + "-" + "<" * n + "#/)"

    body = "}" + preload + "}" + multiply + reads + "}" + retire
    top = [" "] * (len(body) + 2)
    ret = [" "] * (len(body) + 2)
    for i, char in enumerate(body):
        top[i] = char
    # each ring's return leg: '^'.
    first = 1 + len(preload)
    ret[first] = "^"
    ret[first + 1 + multiply.index("/")] = "{"
    second = len(body) - len(retire) - 1
    ret[second] = "^"
    ret[second + 1 + retire.index("/")] = "{"
    return ["".join(top).rstrip(), "".join(ret).rstrip()], len(body)


# Rotating or mirroring a.
# ops are direction-agnostic.
# an orientation.
# into a downward one, which is.
# tall instead.
_LASER_ROTATE = str.maketrans(
    {
        "/": "\\",
        "\\": "/",
        "_": "|",
        "|": "_",
        "(": ")",
        ")": "(",
        "{": "^",
        "}": "v",
        "^": "}",
        "v": "{",
    }
)


def _laserfuck_rotate(rows: list[str]) -> list[str]:
    r"""Turn ``rows`` a quarter turn, so a rightward block becomes downward."""
    height = len(rows)
    width = max(len(line) for line in rows)
    padded = [line.ljust(width) for line in rows]
    return [
        "".join(padded[height - 1 - row][col] for row in range(height)).translate(
            _LASER_ROTATE
        )
        for col in range(width)
    ]


_LASER_FLIP_H = str.maketrans({"/": "\\", "\\": "/", "{": "}", "}": "{"})


def _laserfuck_flip(rows: list[str]) -> list[str]:
    r"""Mirror ``rows`` left to right, so a rightward block runs leftward."""
    width = max(len(line) for line in rows)
    return [line.ljust(width)[::-1].translate(_LASER_FLIP_H) for line in rows]


def _laserfuck_reader_blocks(
    n: int,
    perm: tuple[int, ...] | None = None,
) -> list[list[str]]:
    r"""Cut the flat reader into rectangles, padded so a rotation is exact."""
    rows, _ = _laserfuck_ring_reader(n, perm)
    width = max(len(line) for line in rows)
    padded = [line.ljust(width) for line in rows]
    starts = [col for col, char in enumerate(padded[0]) if char == "}"]
    return [
        [
            line[start : starts[index + 1] if index + 1 < len(starts) else width]
            for line in padded
        ]
        for index, start in enumerate(starts)
    ]


class _LaserBlock(NamedTuple):
    r"""A reader ring placed in one of its two orientations."""

    rows: list[str]
    top: int
    connectors: list[tuple[int, int, str]]
    exit_row: int
    exit_col: int


def _laserfuck_place(block: list[str], upright: str) -> _LaserBlock:
    r"""Give ``block`` an explicit entry/exit contract in one orientation."""
    if upright == "F":
        return _LaserBlock(block, 0, [], 0, len(block[0]))

    turned = _laserfuck_rotate(block)
    entry = turned[0].index("v")
    below = 1 + len(turned)
    # drop in from above, and turn.
    connectors = [(0, entry, "v"), (below, entry, "\\")]
    return _LaserBlock(turned, 1, connectors, below, entry + 1)


def _laserfuck_placements(
    n: int,
    perm: tuple[int, ...] | None = None,
) -> list[dict[str, _LaserBlock]]:
    r"""Place every reader block in *both* orientations, once."""
    return [
        {upright: _laserfuck_place(block, upright) for upright in "FR"}
        for block in _laserfuck_reader_blocks(n, perm)
    ]


def _laserfuck_assemble_reader(
    placements: list[dict[str, _LaserBlock]],
    orientation: str,
) -> tuple[list[str], int, int]:
    r"""Chain the reader's blocks, each flat (``F``) or on end (``R``)."""
    cells: dict[tuple[int, int], str] = {}

    def put(row: int, col: int, char: str) -> None:
        if char != " ":
            cells[(row, col)] = char

    row = col = 0
    for choices, upright in zip(placements, orientation, strict=True):
        placed = choices[upright]
        for offset, line in enumerate(placed.rows):
            for index, char in enumerate(line):
                put(row + placed.top + offset, col + index, char)
        for offset, index, char in placed.connectors:
            put(row + offset, col + index, char)
        row += placed.exit_row
        col += placed.exit_col

    # Render row by row from the.
    # the bounding rectangle.
    # for a grid that is mostly.
    # the generator's hot path --.
    # fraction of that.
    # columns actually present.
    # in time proportional to the.
    height = max(r for r, _ in cells) + 1
    rows: list[list[tuple[int, str]]] = [[] for _ in range(height)]
    for (r, c), char in cells.items():
        rows[r].append((c, char))
    lines = []
    for marks in rows:
        marks.sort()
        parts: list[str] = []
        cursor = 0
        for c, char in marks:
            if c > cursor:
                parts.append(" " * (c - cursor))
            parts.append(char)
            cursor = c + 1
        lines.append("".join(parts))
    return lines, row, col


_ReaderCandidate = tuple[int, int, tuple[str, ...], int, int]


@cache
def _laserfuck_reader_candidates(
    n: int,
    perm: tuple[int, ...] | None = None,
) -> tuple[_ReaderCandidate, ...]:
    r"""Every orientation word's reader, shortest first, as ``(rows, span,."""
    placements = _laserfuck_placements(n, perm)
    count = len(placements)
    candidates = []
    for choice in range(2**count):
        orientation = "".join("R" if choice >> b & 1 else "F" for b in range(count))
        rows_of, exit_row, exit_col = _laserfuck_assemble_reader(
            placements, orientation
        )
        span = max(len(line) for line in rows_of)
        candidates.append((len(rows_of), span, tuple(rows_of), exit_row, exit_col))
    # Stable, so ties still break.
    candidates.sort(key=lambda item: (item[0], item[1]))
    return tuple(candidates)


def _laserfuck_build(
    truth_table: str,
    perm: tuple[int, ...],
    width: int | None = None,
) -> str:
    r"""Build one LaserFuck program, reading its inputs in ``perm`` order."""
    n = _validate_truth_table(truth_table)
    # The tree adds only a column.
    # what a width has to bargain.
    # and forty-odd columns,.
    candidates = _laserfuck_reader_candidates(n, perm)
    fitting = [
        item
        for item in candidates
        if width is None or laserfuck_layout.MARGIN + item[1] + 2 <= width
    ]
    chosen = fitting[0] if fitting else min(candidates, key=lambda item: item[1])
    _, _, reader_rows, reader_exit_row, reader_exit_col = chosen

    margin = laserfuck_layout.MARGIN
    grid: list[list[str]] = []

    def put(row: int, col: int, char: str) -> None:
        r"""Write one cell, growing the ragged grid to reach it."""
        if len(grid) <= row:
            grid.extend([] for _ in range(row + 1 - len(grid)))
        line = grid[row]
        # The layout fills each row.
        # already in range and this.
        if len(line) <= col:  # pragma: no branch
            line.extend(" " * (col + 1 - len(line)))
        line[col] = char

    def put_run(row: int, col: int, text: str) -> None:
        r"""Write a whole run of cells, growing the ragged grid to reach it."""
        if len(grid) <= row:
            grid.extend([] for _ in range(row + 1 - len(grid)))
        line = grid[row]
        if len(line) < col:
            line.extend(" " * (col - len(line)))
        line[col : col + len(text)] = text

    # The funnel: every start.
    # (0, 0) stays blank so the.
    put(0, 1, "}")
    put(0, 2, "}")
    put(1, 0, "|")
    put(1, 1, "o")
    put(1, 2, "^")
    put(2, 1, "_")

    # The rings go on rows 0 and 1;.
    # with the pointer on cell 0.
    for offset, text in enumerate(reader_rows):
        for index, char in enumerate(text):
            if char != " ":
                put(offset, margin + index, char)
    # The beam leaves the reader.
    # its own for the tree.
    # block left beneath it: a.
    # on the row below, which the.
    # at its own foot with nothing.
    # The tree is built as a block.
    # the reader.
    # beam leaves the reader at its.
    # would be needed to carry it.
    # start.
    # is, so that whole row.
    # reader's end and a '/' faces.
    # .
    # Within the tree a node writes.
    # way in, so ')' tests the cell.
    # straight through and the next.
    # one turns the beam back onto.
    # faces it right again on a.
    # number of *one* edges rather.
    # all-zeros path is a single.
    # The tree as ``(column,.
    # character.
    # from ``><-+`` and the rest.
    # ``\`` -- and every row is.
    # the whole of what a cell dict.
    # The order search rebuilds.
    # 1.7M single-cell writes going.
    # out over the bounding.
    # tree is a staircase.
    # .
    # A row is appended exactly.
    # counter that names it is.
    # is the next row index and the.
    rows: list[list[tuple[int, str]]] = [[]]

    def emit(path: list[int], row: int, col: int) -> None:
        r"""Lay the subtree for ``path``, entered at ``(row, col)`` going right."""
        depth = len(path)
        first = int("".join(map(str, path)), 2) << (n - depth) if path else 0
        if depth == n or len(set(truth_table[first : first + 2 ** (n - depth)])) == 1:
            index = first
            # The rings leave the inputs in.
            # touched at zero, so the sweep.
            # answer needs no code at all.
            # cells however deep the leaf.
            # 1 and would print beside the.
            # ``depth``, so step out to.
            # .
            # Cells above ``depth`` were.
            # unknown here and two ``-``.
            # -1).
            # sized run of one ``-`` more.
            # table that folds nothing.
            run = ">" * (n - depth)
            run += "--<" * (n - depth)
            for level in range(depth, 0, -1):
                run += "-" * (path[level - 1] + 1) + "<"
            run += "+" if truth_table[index] == "1" else ""
            rows[row].append((col, run + "x"))
            return
        rows[row].append((col, ">#v)"))
        emit([*path, 0], row, col + 4)  # a zero carries on along this.
        drop = len(rows)
        rows.append([(col + 2, "\\")])  # a one comes down the 'v'.
        emit([*path, 1], drop, col + 3)

    emit([], 0, 0)
    span = max(col + len(text) for marks in rows for col, text in marks)
    upright = []
    for marks in rows:
        parts: list[str] = []
        cursor = 0
        for col, text in marks:
            if col > cursor:
                parts.append(" " * (col - cursor))
            parts.append(text)
            cursor = col + len(text)
        parts.append(" " * (span - cursor))
        upright.append("".join(parts))

    # Where the tree goes depends.
    # .
    # The beam leaves the reader.
    # is to carry straight on: the.
    # the reader's own rows, and.
    # tree itself needs.
    # reader and the tree laid end.
    # .
    # Otherwise the tree is.
    # down at the reader's end and.
    # left into a tree that runs.
    # *reached*, unlike a rightward.
    # carry the beam back to the.
    straight = margin + reader_exit_col + max(len(line) for line in upright)
    if width is None or straight + 1 <= width:
        # Laid from the runs, not from.
        # staircase, so ``upright`` is.
        # re-padded by the next run on.
        # end) rather than written.
        for offset, marks in enumerate(rows):
            for col, text in marks:
                put_run(reader_exit_row + offset, margin + reader_exit_col + col, text)
    else:
        flipped = _laserfuck_flip(upright)
        entry = len(flipped[0].rstrip()) - 1
        # A narrow reader can leave the.
        # wide, and the tree would run.
        # further to the right costs.
        # so the fall column is pushed.
        fall = max(margin + reader_exit_col, margin + entry + 1)
        # The tree hangs on the first.
        # falls to reach it depends on.
        # exit -- a flat block keeps.
        # rotated one ends at its own.
        # own last occupied row either.
        # height, and the orientation.
        top = len(reader_rows)
        put(reader_exit_row, fall, "v")
        for offset, line in enumerate(flipped):
            for index, char in enumerate(line):
                put(top + offset, fall - 1 - entry + index, char)
        put(top, fall, "/")

    lines = ["".join(line).rstrip() for line in grid]
    while lines and not lines[-1]:
        lines.pop()  # pragma: no cover - the grid ends on content
    return "\n".join(lines)


def laserfuck(truth_table: str, width: int | None = None) -> str:
    r"""Build a LaserFuck program computing the given truth table."""
    n = _validate_truth_table(truth_table)
    identity = tuple(range(n))
    orders = [identity]
    if n <= _ORDER_SEARCH_MAX:
        orders += [p for p in permutations(range(n)) if p != identity]

    best = _laserfuck_build(truth_table, identity, width)
    for perm in orders[1:]:
        candidate = _laserfuck_build(
            permute_truth_table(truth_table, perm), perm, width
        )
        if len(candidate) < len(best):
            best = candidate
    return best
