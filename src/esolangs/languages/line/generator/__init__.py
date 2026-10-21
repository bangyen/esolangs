"""Line Boolean program generator: a ``?`` tree over inputs read into cells.

Line's ``i`` reads a whole number and ``o`` prints one, so 0/1 is what ``IO``
hands over and no ASCII offset enters.  Reads each input into its own cell,
then walks a ``?`` tree testing only the inputs its subtree depends on:
through five inputs a level whose halves agree is skipped, so a constant is
one leaf and an ignored input is read but never tested; from six inputs
every level is tested, the skipped tree's extents growing past the tested
tree's there.  A leaf prints the cell it just tested, after
one ``+`` or ``-`` when the entry differs from that bit; a constant prints the
unread cell ``n``.  Arms use measured subtree extents with one cell of
clearance for forward-only subtrees, two otherwise.

Candidates compete by emitted area; the smallest wins:

- Projected loader: stores only essential inputs; ignored reads overwrite the
  next kept slot, or one spare slot after the last kept input.
- Ordered residual folds: share forward joins; the saved loader rewind pays
  for join transitions, and measured area must beat the tree.  Shared
  destination moves allow narrower nonterminal forks.
- Input-order streaming: shares reads on stems, overwriting cell zero and
  draining constant tails; its fresh output cell stays within the original
  tape.

Complete folds win fallback area ties; larger drawings retain the smaller
fallback.

Size:
    Parity and and grow linearly in n, random in T; n=10 parity: 1,892,800
    codels, n=10 and: 1,691,200 codels, n=8 random 1847: 16,147,200 codels.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from functools import lru_cache, partial
from typing import NamedTuple, cast

from esolangs.generation.helpers import (
    _residual_ids,
    _validate_truth_table,
    essential_inputs,
    permute_truth_table,
    read_at,
)
from esolangs.languages.line.generator.forward import streaming_canvas
from esolangs.languages.line.generator.layout import (
    Node,
    _has_goto,
    _moved,
    chain,
    chain_onto,
    correction,
    loader_reads,
)
from esolangs.languages.line.generator.render import _UNIT, Canvas, _check_unit
from esolangs.languages.line.generator.shared import CanvasPlan
from esolangs.languages.line.generator.small_tree import small_tree_canvas
from esolangs.languages.line.generator.tree_layout import tree_extents
from esolangs.languages.line.proof_formulas import workspace
from esolangs.raster import Pixel, Raster, Rows, lazy_raster
from esolangs.registry._language import Language, SourceKind


def line_boolean(
    truth_table: str, *, reverse: bool = False, skip: bool | None = None
) -> Node:
    """Build a Line program computing ``truth_table`` (see module docstring).

    Returns a :class:`layout.Node` graph for :func:`render.render`; Line has no text.
    ``skip`` descends a level whose residual halves agree without testing
    it; the default scopes it to n <= 5: from n=6 the skipped tree's extents
    grow past the tested tree's ([ablations.level_skip]).
    """
    n = _validate_truth_table(truth_table)
    if skip is None:
        skip = n <= _SMALL_MAX
    order = tuple(range(n - 1, -1, -1)) if reverse else tuple(range(n))
    if reverse:
        truth_table = permute_truth_table(truth_table, order)
    levels, children, _ = _residual_ids(truth_table, n)

    # Read n inputs into cells 0..n-1, one `i` per cell, `>` between them.
    head = chain(*("i" + ">i" * (n - 1)))

    def fork(state: int, depth: int, pointer: int, known: int | None) -> Node:
        while skip and depth < n and children[state][0] == children[state][1]:
            state = children[state][0]
            depth += 1
        if depth == n:
            value = state
            if known is None:
                return _moved(pointer, n, chain(*(["+"] * value), "o"))
            return chain(*correction(value, known), "o")
        node = Node("?")
        cell = order[depth]
        zero, one = children[state]
        node.zero = fork(zero, depth + 1, cell, 0)
        node.nonzero = fork(one, depth + 1, cell, 1)
        return _moved(pointer, cell, node)

    chain_onto(head, fork(levels[0][0], 0, n - 1, None))
    return head


def projected_boolean(truth_table: str, *, reverse: bool = False) -> Node | None:
    """Store only essential inputs, overwriting the next kept slot for ignores."""
    n = _validate_truth_table(truth_table)
    kept = essential_inputs(truth_table, n)
    if len(kept) == n:
        return None
    if not kept:
        return chain(*("i" * n + ">" + "+" * int(truth_table[0]) + "o"))
    reduced = read_at(truth_table, kept, n)
    # The skip scope keys on the original table's arity, not the reduced one.
    return _project_loader(
        n, kept, line_boolean(reduced, reverse=reverse, skip=n <= _SMALL_MAX)
    )


def _project_loader(n: int, kept: list[int], node: Node) -> Node:
    for _ in range(2 * len(kept) - 1):
        if node.next is None:
            raise ValueError("projected Line tree has no decision body")
        node = node.next
    # Enter the unchanged reduced decision body from the final kept cell.
    head = chain(*loader_reads(n, kept))
    chain_onto(head, node)
    return head


_SMALL_MAX = 5  # tight tree layout through n=5 (see small_tree)
_BOOLEAN_UNIT = _UNIT
_GREY_RUN = re.compile(rb"(.)\1*", re.DOTALL)


def _render_node(
    node: Node,
    *,
    compact: bool = True,
    tight: bool = True,
    unit: int = _BOOLEAN_UNIT,
) -> Rows:
    """Render a generated Line graph into shared RGB rows."""
    # Local: a top-level `render` would shadow the submodule on the package.
    from esolangs.languages.line.generator.render import render

    return _grey_rows(
        render(
            node,
            acyclic=True,
            compact=compact,
            tight=tight,
            unit=unit,
        )
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


class _Candidate(NamedTuple):
    """Smallest layout so far; ``rows`` draws it only when the raster is read."""

    node: Node
    area: int
    rows: Callable[[], Rows]
    complete: bool = False


def _planned_rows(plan: CanvasPlan) -> Rows:
    """Run a deferred canvas plan into shared RGB rows."""
    return _grey_rows(plan())


@lru_cache(maxsize=8)
def _generate(truth_table: str, unit: int = _BOOLEAN_UNIT) -> Raster:
    """Return a Line raster computing ``truth_table``."""
    _check_unit(unit)
    n = _validate_truth_table(truth_table)

    def candidate(tree: Node) -> _Candidate:
        if n <= _SMALL_MAX and (drawn := small_tree_canvas(tree, unit=unit)):
            return _Candidate(
                tree, drawn.width * drawn.height, partial(_grey_rows, drawn)
            )
        top, bottom, left, right = tree_extents(tree)[id(tree)]
        return _Candidate(
            tree,
            (bottom - top + 2) * (right - left + 2) * unit**2,
            partial(_render_node, tree, unit=unit),
        )

    best = candidate(line_boolean(truth_table))
    # Projected tree, by area: with one or two essential inputs 17-25% (n=8..11,
    # 40 tables each), constants 20-38%; three to five 2-7%, pooled over one to
    # n-1 essential 7.9-9.1% (n=7..10, ~200 tables each).  A majority-3 core in
    # 8 inputs: 13%.  Kept as one candidate rather than split by essential count.
    projected = projected_boolean(truth_table)
    if projected is not None:
        other = candidate(projected)
        if other.area < best.area:
            best = other
    # Streaming saves 0% on random tables at n>=8 (0.45% at n=7) but 23-96% on
    # parity, and, majority and thresholds (n=6..12).
    # A complete fold wins a fallback tie.
    fold = streaming_canvas(truth_table, best.area + 1, unit=unit)
    if fold is not None:
        best = _Candidate(
            fold[0], fold[1].area, partial(_planned_rows, fold[1]), complete=True
        )
    return lazy_raster(best.rows, best.node)


def line(truth_table: str, *, scale: int = 1, unit: int = _BOOLEAN_UNIT) -> Raster:
    """Return a Line raster enlarged by an integer pixel factor."""
    return _generate(truth_table, unit).upscaled(scale)


class _Score(NamedTuple):
    """Orders layouts by enclosing side, then area, then width (0 when small)."""

    side: int
    area: int
    tiebreak: int


class _Choice(NamedTuple):
    score: _Score
    node: Node
    canvas: Canvas | None
    compact: bool
    tight: bool


def _best_choice(
    options: list[Node], *, compact: bool, tight: bool = True, small: bool, unit: int
) -> _Choice:
    """Return the most balanced option."""
    choices = []
    for node in options:
        canvas = (
            small_tree_canvas(node, compact=compact, tight=tight, unit=unit)
            if small
            else None
        )
        if canvas is not None:
            width, height = canvas.width, canvas.height
        else:
            y0, y1, x0, x1 = tree_extents(node, compact=compact, tight=tight)[id(node)]
            width, height = (x1 - x0 + 2) * unit, (y1 - y0 + 2) * unit
        score = _Score(max(width, height), width * height, 0 if small else width)
        choices.append(_Choice(score, node, canvas, compact, tight))
    return min(choices, key=lambda choice: choice.score)


def _balanced_choice(truth_table: str, *, small: bool, unit: int) -> _Choice:
    """Most balanced compact tree over the previous and projected trees."""
    previous = [line_boolean(truth_table, reverse=reverse) for reverse in (False, True)]
    nodes = previous + [
        projected
        for reverse in (False, True)
        if (projected := projected_boolean(truth_table, reverse=reverse)) is not None
    ]
    chosen = _ceilinged_choice(nodes, small=small, unit=unit)
    if small:
        return chosen
    # Skipped trees stay candidates past five inputs: compact, they balance
    # OR n=8 to 900x1880 where the tested tree gives 3480x4440.  Raced as a
    # second pool so the area rules never make the tested choice worse.
    skipped = [
        line_boolean(truth_table, reverse=reverse, skip=True)
        for reverse in (False, True)
    ]
    other = _ceilinged_choice(nodes + skipped, small=small, unit=unit)
    return min(chosen, other, key=lambda choice: choice.score)


def _ceilinged_choice(nodes: list[Node], *, small: bool, unit: int) -> _Choice:
    """Most balanced compact node, capped by the untightened layout's area."""
    preceding = _best_choice(nodes, compact=True, tight=False, small=small, unit=unit)
    chosen = _best_choice(nodes, compact=True, small=small, unit=unit)
    # Winning on side can still grow the area: 00011100 grows 248087 ->
    # 274287 pixels without this (6 of the 256 n=3 tables).
    if chosen.score.area > preceding.score.area:
        chosen = preceding
    return chosen


def balance(truth_table: str, default: Raster, *, unit: int = _BOOLEAN_UNIT) -> Raster:
    """Choose the most balanced compact or previous forward/reverse tree."""
    _check_unit(unit)
    small = _validate_truth_table(truth_table) <= _SMALL_MAX
    score, selected, canvas, compact, tight = _balanced_choice(
        truth_table, small=small, unit=unit
    )
    width = canvas.width if canvas is not None else score.tiebreak
    if _has_goto(cast("Node | None", default._payload)):  # noqa: SLF001 - generator-owned graph
        height, shared_width = len(default.rows), len(default.rows[0])
        shared_area = shared_width * height
        if (max(shared_width, height), shared_area, shared_width) <= (
            score.side,
            score.area,
            width,
        ) and shared_area <= score.area:
            return default
    return lazy_raster(
        lambda: (
            _grey_rows(canvas)
            if canvas is not None
            else _render_node(selected, compact=compact, tight=tight, unit=unit)
        ),
        selected,
    )


LANGUAGE = Language(
    "Line",
    "line",
    category="tape_based",
    # A 2^12-row raster renders in about 24s.
    slow_scaling=True,
    source_kind=SourceKind.RASTER,
    boolean=line,
    balance=balance,
    no_wrap="tree geometry fixes the width; balance chooses orientation",
    empty_program="image contains no ink",
    proof_workspace=(workspace, True, (5,)),
)
