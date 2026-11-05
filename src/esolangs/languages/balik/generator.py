"""Balik Boolean program generator: nested boxes, one test per input.

The first row reads every essential input into its own cell, 0 first, and
each ignored one into a junk cell past the answer cell.  Each box tests one
cell with ``*`` over ``@``: on 0 the pointer reverses into the top child,
otherwise it runs down to the bottom child.  Both children leave east into a
second ``*`` over ``@`` that merges them, since the tested cell is
unchanged.  A leaf prints the answer cell, incremented for a 1.  Boxes
stack children vertically, and side by side at every other level, so the
area is linear.

Size:
    Theta(T) area; n=4 parity: 685 chars.
    Constants: n + 2/3 cells and commands.

Decisions:
    A constant subtable is one leaf that walks to the answer cell, so a
    sibling box may be narrower or shorter: the path crosses spaces.
    A global input negation (``++`` after each read, reversed table) wins
    only reversed thresholds (n=10 thr2 15,197 -> 12,101 chars), never a
    random table, and grows their balanced area up to a third: not built.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from esolangs.generation.helpers import (
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    read_at,
)
from esolangs.languages.balik.descriptor import LANGUAGE as LANGUAGE


@dataclass
class _Cells:
    """Translated children avoid copying every glyph at every ancestor."""

    local: dict[tuple[int, int], str] = field(default_factory=dict)
    children: list[tuple["_Cells", int, int]] = field(default_factory=list)


type _Box = tuple[_Cells, int, int]


def _put(cells: _Cells, row: int, col: int, text: str) -> None:
    for i, c in enumerate(text):
        assert (row, col + i) not in cells.local, (row, col + i)
        cells.local[row, col + i] = c


def _merge(cells: _Cells, child: _Cells, row: int, col: int) -> None:
    cells.children.append((child, row, col))


def _box(
    table: str, constant: Callable[[int, int], bool], start: int, stop: int, k: int
) -> _Box:
    """Return a box entered heading east at its top-left, left east on row 0."""
    depth = k - (stop - start).bit_length() + 1
    if constant(start, stop):
        walk = k - depth
        leaf = ">" * walk + ("+." if table[start] == "1" else ".") + "<" * walk
        return _Cells({(0, i): c for i, c in enumerate(leaf)}), len(leaf), 1
    # The final input is already the requested 0/1 answer; its cell is
    # unchanged, preserving the enclosing box's merge test.
    if stop - start == 2 and table[start:stop] == "01":
        return _Cells({(0, 0): "."}), 1, 1
    half = (start + stop) // 2
    top, w0, h0 = _box(table, constant, start, half, k)
    bottom, w1, h1 = _box(table, constant, half, stop, k)
    cells = _Cells()
    # The split: a 0 reverses at ``@`` into ``*``, which turns east.
    _put(cells, 0, 1, "*>")
    _put(cells, 1, 1, "@")
    _merge(cells, top, 0, 3)
    levels = k - depth
    # Side by side only at odd levels from 3 below the root: the least
    # area over every layout sequence through n = 14 (n = 4 within 1%).
    if not (levels % 2 and 3 <= levels < k):
        # Vertical: the bottom child under the top one.
        b = max(w0, w1) + 4
        # With two leaves, the nonzero branch can cross the splitter @
        # eastward: it neither turns nor changes the tested cell.
        r1 = 1 if h0 == h1 == 1 else max(h0, 2)
        _put(cells, 0, b - 1, "<*")
        _put(cells, 1, b, "@")
        _put(cells, r1, 0, "*")
        _put(cells, r1 + 1, 0, "**")
        _put(cells, r1, 2, ">")
        _merge(cells, bottom, r1, 3)
        _put(cells, r1, b - 1, "<")
        _put(cells, r1, b + 1, "*")
        _put(cells, r1 + 1, b, "**")
        return cells, b + 2, r1 + max(h1, 2)
    # Horizontal: the bottom child beside the top one, entered from below.
    x = w0 + 5
    r = max(h0, 3)
    b = x + w1 + 1
    _put(cells, 0, b - 1, "<*")
    _put(cells, 1, b, "@")
    _put(cells, r, 0, "*")
    _put(cells, r + 1, 0, "**")
    _put(cells, r, x - 1, "*")
    _put(cells, r + 1, x - 2, "**")
    _put(cells, 2, x - 2, "*>")
    _merge(cells, bottom, 2, x)
    _put(cells, 2, x + w1, "<")
    _put(cells, 2, b + 1, "*")
    _put(cells, 3, b, "**")
    return cells, b + 2, max(h1 + 2, r + 2)


def balik(truth_table: str) -> str:
    """Build a Balik program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    if truth_table.count(truth_table[0]) == len(truth_table):
        return "," * n + ">" + "+" * int(truth_table[0]) + "."
    essential = essential_inputs(truth_table, n)
    k = len(essential)
    # Essential input j goes to cell j; ignored ones to cell k + 1, past
    # the answer cell k.
    prefix = []
    at = 0
    for i in range(n):
        cell = essential.index(i) if i in essential else k + 1
        prefix.append(">" * (cell - at) + "<" * (at - cell) + ",")
        at = cell
    prefix.append("<" * at)
    head = "".join(prefix)
    table = read_at(truth_table, essential, n)
    cells, _, height = _box(table, constant_span_test(table), 0, len(table), k)
    rows: list[dict[int, str]] = [{} for _ in range(height)]
    grid = _Cells({(0, i): c for i, c in enumerate(head)})
    _merge(grid, cells, 0, len(head))
    pending = [(grid, 0, 0)]
    while pending:
        node, row, col = pending.pop()
        for (r, c), ch in node.local.items():
            target = rows[row + r]
            assert col + c not in target, (row + r, col + c)
            target[col + c] = ch
        pending.extend((child, row + r, col + c) for child, r, c in node.children)
    return "\n".join(
        "".join(row.get(c, " ") for c in range(max(row, default=-1) + 1))
        for row in rows
    )
