"""Build a Line program computing a given boolean truth table directly.

No brainfuck intermediate: Line's ``i`` reads a whole number and ``o``
prints one, so 0/1 is exactly what ``IO`` hands over and no ASCII offset
enters.  The program reads each input into its own cell, then walks a ``?``
tree that tests only the inputs its subtree depends on: a level whose
halves agree is skipped, so a constant is one leaf and an ignored input
is read but never tested.  A leaf prints the cell it just tested, after
one ``+`` or ``-`` when the entry differs from that bit; a constant has no
test and prints the unread cell ``n``.  ``truth_table`` is a binary string of
length ``2**n``, MSB first.  Arms use measured subtree extents with a
two-cell gap. A bounded ancestor return shares a repeated nonconstant
residual when it saves area within 5n commands: clear a consumed input
and re-enter its zero arm. Reads and the tape footprint stay unchanged.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import cast

from esolangs.raster import Pixel, Raster, Rows, lazy_raster
from esolangs.registry._language import Language, SourceKind
from esolangs.tools.helpers import (
    _residual_ids,
    _validate_truth_table,
    permute_truth_table,
)
from esolangs.tools.line.render import _UNIT, Canvas, Node, chain
from esolangs.tools.line.small_tree import small_tree_canvas
from esolangs.tools.line.tree_layout import tree_extents


def line_boolean(truth_table: str, *, reverse: bool = False) -> Node:
    """Build a Line program computing ``truth_table`` (see module docstring).

    Returns a :class:`render.Node` graph for :func:`render.render`; Line has no text.
    """
    n = _validate_truth_table(truth_table)
    order = tuple(range(n - 1, -1, -1)) if reverse else tuple(range(n))
    if reverse:
        truth_table = permute_truth_table(truth_table, order)
    levels, children, _ = _residual_ids(truth_table, n)

    # Read n inputs into cells 0..n-1, one `i` per cell, `>` between them.
    head = Node("i")
    tail = head
    for _ in range(n - 1):
        move = Node(">")
        tail.next = move
        read = Node("i")
        move.next = read
        tail = read

    def moved(pointer: int, cell: int, rest: Node) -> Node:
        """Prefix ``rest`` with the moves from ``pointer`` to ``cell``."""
        step = ">" if cell > pointer else "<"
        for _ in range(abs(cell - pointer)):
            rest = Node(step, next=rest)
        return rest

    def fork(state: int, depth: int, pointer: int, known: int | None) -> Node:
        while depth < n and children[state][0] == children[state][1]:
            state = children[state][0]
            depth += 1
        if depth == n:
            value = state
            if known is None:
                return moved(pointer, n, chain(*(["+"] * value), "o"))
            step = {1: ["+"], 0: [], -1: ["-"]}[value - known]
            return chain(*step, "o")
        node = Node("?")
        cell = order[depth]
        zero, one = children[state]
        node.zero = fork(zero, depth + 1, cell, 0)
        node.nonzero = fork(one, depth + 1, cell, 1)
        return moved(pointer, cell, node)

    tail.next = fork(levels[0][0], 0, n - 1, None)
    return head


_SMALL_MAX = 5  # tight tree layout through n=5 (see small_tree)
_GREY_RUN = re.compile(rb"(.)\1*", re.DOTALL)


def _render_node(
    node: Node, heading: tuple[int, int] = (-1, 0), *, compact: bool = True
) -> Rows:
    """Render a generated Line graph into shared RGB rows."""
    # Local: a top-level `render` would shadow the submodule on the package.
    from esolangs.tools.line.render import render

    return _grey_rows(
        render(node, start_heading=heading, acyclic=True, compact=compact)
    )


def _grey_rows(canvas: Canvas) -> Rows:
    """Expand a greyscale canvas into shared RGB rows."""
    palette = tuple((level, level, level) for level in range(256))
    cache: dict[bytes, tuple[Pixel, ...]] = {}
    rows = []
    for row in canvas.pixels:
        key = bytes(row)
        pixels = cache.get(key)
        if pixels is None:
            expanded = []
            for run in _GREY_RUN.finditer(key):
                expanded.extend([palette[run[1][0]]] * (run.end() - run.start()))
            pixels = tuple(expanded)
            if len(cache) < 1024:
                cache[key] = pixels
        rows.append(pixels)
    return tuple(rows)


@lru_cache(maxsize=8)
def _generate(truth_table: str) -> Raster:
    """Return a Line raster computing ``truth_table``."""
    from .shared import shared_canvas, shared_tree

    node = line_boolean(truth_table)
    n = _validate_truth_table(truth_table)
    shared = shared_tree(truth_table)
    canvas = None
    if shared is not None:
        if n <= _SMALL_MAX:
            canvas = small_tree_canvas(node)
            area = canvas.width * canvas.height
        else:
            top, bottom, left, right = tree_extents(node)[id(node)]
            area = (bottom - top + 2) * (right - left + 2) * _UNIT**2
        draw = shared_canvas(shared[0], area)
        if draw is not None:
            return lazy_raster(lambda: _grey_rows(draw()), shared[0])
    if canvas is not None:
        return lazy_raster(lambda: _grey_rows(canvas), node)
    if n <= _SMALL_MAX:
        return lazy_raster(lambda: _grey_rows(small_tree_canvas(node)), node)
    return lazy_raster(lambda: _render_node(node), node)


def line(truth_table: str, *, scale: int = 1) -> Raster:
    """Return a Line raster enlarged by an integer pixel factor."""
    return _generate(truth_table).upscaled(scale)


def balance(truth_table: str, default: Raster) -> Raster:
    """Choose the most balanced compact or previous forward/reverse tree."""

    def score(node: Node, *, compact: bool) -> tuple[int, int, int]:
        y0, y1, x0, x1 = tree_extents(node, compact=compact)[id(node)]
        width, height = (x1 - x0 + 2) * _UNIT, (y1 - y0 + 2) * _UNIT
        return abs(width - height), width * height, width

    def retain_shared(score: tuple[int, int, int]) -> bool:
        from .render import _has_goto

        if not _has_goto(cast("Node | None", default._payload)):  # noqa: SLF001 - generator-owned graph
            return False
        height, width = len(default.rows), len(default.rows[0])
        return (
            abs(width - height),
            width * height,
            width,
        ) <= score and width * height <= score[1]

    nodes = [line_boolean(truth_table, reverse=reverse) for reverse in (False, True)]
    if _validate_truth_table(truth_table) <= _SMALL_MAX:
        drawn = [(small_tree_canvas(node), node) for node in nodes]

        def canvas_score(pair: tuple[Canvas, Node]) -> tuple[int, int]:
            canvas, _ = pair
            return abs(canvas.width - canvas.height), canvas.width * canvas.height

        previous = [(small_tree_canvas(node, compact=False), node) for node in nodes]
        old = min(previous, key=canvas_score)
        candidate = min(drawn, key=canvas_score)
        # Shorter stems can select a wider orientation: 00010101 grows
        # 209277 -> 248087 pixels. Preserve the preceding area ceiling.
        chosen = (
            candidate
            if (
                canvas_score(candidate) <= canvas_score(old)
                and canvas_score(candidate)[1] <= canvas_score(old)[1]
            )
            else old
        )
        canvas, node = chosen
        if retain_shared(
            (
                abs(canvas.width - canvas.height),
                canvas.width * canvas.height,
                canvas.width,
            )
        ):
            return default
        return lazy_raster(lambda: _grey_rows(canvas), node)
    compact_score, selected = min(
        ((score(node, compact=True), node) for node in nodes), key=lambda p: p[0]
    )
    old_score, old_selected = min(
        ((score(node, compact=False), node) for node in nodes), key=lambda p: p[0]
    )
    # 01101110 ties in imbalance but grows 1,187,200 -> 1,276,000 pixels.
    compact = compact_score <= old_score
    if not compact:
        selected = old_selected
    if retain_shared(min(compact_score, old_score)):
        return default
    return lazy_raster(lambda: _render_node(selected, compact=compact), selected)


LANGUAGE = Language(
    "Line",
    "tape_based.line",
    weekly_mutation=("interpreter", "generator"),
    # A 2^12-row raster renders in about 24s.
    slow_scaling=True,
    source_kind=SourceKind.RASTER,
    boolean=line,
    balance=balance,
    no_wrap="tree geometry fixes the width; balance chooses orientation",
    empty_program="image contains no ink",
)
