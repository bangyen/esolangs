"""thisthat Boolean program generator: a bistack-routed planar decision tree.

A loader reads each input and pushes essential bits to the bistack; each node
pops one and routes by a ``◒``/``◑`` router; a final mixed pair emits
its bit or NOT directly. Ignored inputs only read. Every
kept input is tested at every node.  A bounded DAG replaces the tree when
smaller; narrow widths try rotation, strips and streaming trees.

Size:
    Linear area in T for the plain tree; n=8 parity: 6,139 chars, n=10 and:
    2,367 chars, n=10 random 1847: 36,199 chars. Constants: 2n+5 cells
    and cycles; the balanced chain folds without adding transit cells.

Decisions:
    Greedy input order saves 0.2% at n=8 and swapping the root's arms 0.5%,
    both under the 10% bar.
"""

from collections.abc import Sequence
from functools import cached_property
from itertools import pairwise
from math import isqrt
from typing import Literal

from esolangs.generation.grid import grid_area, grid_rank, grid_width, narrowest_grid
from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.lookup import constant_output
from esolangs.generation.projection import essential_inputs, read_at
from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import balance_score
from esolangs.languages.thisthat._drawing import (
    _DOUBLE,
    _SINGLE,
    _Builder,
    _draw_loader,
    _first_axis,
    _path,
)
from esolangs.languages.thisthat._shared import _MIN_NODE_BUDGET, _draw_shared
from esolangs.runtime._program import Program

type _Point = tuple[int, int]
#: One child of a tree node: its span, its point, and its walk context.
type _Child = tuple[int, int, _Point, _Point]


class _TreeEmitter:
    """A planar decision tree: one walk, with each form's geometry as hooks.

    The walk itself is the same for the streaming, strip and laid-out
    trees: a leaf places its glyph, an exit diamond two steps away, and a
    double wire between them; an internal node places its trunk glyph and
    a router, wires the trunk, then connects each child with a single wire
    and recurses.  What differs is only geometry and glyphs: where the
    router sits, how far the children are pitched, when a span is a leaf,
    and whether equal halves prune the second child.  A form's context is
    whatever its hooks need (the stream's parent point, the layout's
    incoming direction); its leaf exit defaults to its router point, which
    only the stream overrides.
    """

    _trunk = "◧"

    def __init__(self, builder: _Builder, table: str) -> None:
        self._builder = builder
        self._table = table

    def run(self, level: int, lo: int, hi: int, point: _Point, context: _Point) -> None:
        """Emit the node for ``table[lo:hi]`` at ``point`` and its subtree."""
        builder = self._builder
        if self._leaf(level, lo, hi):
            builder.node(point, "■" if self._table[lo] == "1" else "□")
            exit_point = self._exit(point, context)
            builder.node(exit_point, "◇")
            builder.connect(
                _path(point, exit_point, self._leaf_axis(context)), "double"
            )
            return
        router = self._router(point, context)
        builder.node(point, self._trunk)
        builder.node(router, self._router_glyph(level, lo))
        builder.connect(_path(point, router, self._trunk_axis(context)), "double")
        children = self._children(level, lo, hi, router)
        for child_lo, child_hi, child_point, child_context in children:
            builder.connect(
                _path(router, child_point, self._child_axis(level)), "single"
            )
            self.run(level + 1, child_lo, child_hi, child_point, child_context)

    def _leaf(self, level: int, lo: int, hi: int) -> bool:
        raise NotImplementedError

    def _exit(self, point: _Point, context: _Point) -> _Point:
        return self._router(point, context)

    def _router(self, point: _Point, context: _Point) -> _Point:
        raise NotImplementedError

    def _router_glyph(self, level: int, lo: int) -> str:
        raise NotImplementedError

    def _children(self, level: int, lo: int, hi: int, router: _Point) -> list[_Child]:
        raise NotImplementedError

    def _leaf_axis(self, context: _Point) -> Literal["horizontal", "vertical"]:
        raise NotImplementedError

    def _trunk_axis(self, context: _Point) -> Literal["horizontal", "vertical"]:
        raise NotImplementedError

    def _child_axis(self, _level: int) -> Literal["horizontal", "vertical"]:
        return "vertical"


class _StreamTree(_TreeEmitter):
    """The streaming tree: routers mirrored across the node's column."""

    _trunk = "◇"

    def __init__(
        self, builder: _Builder, table: str, ids: Sequence[Sequence[int]], depth: int
    ) -> None:
        super().__init__(builder, table)
        self._ids = ids
        self._depth = depth

    def _leaf(self, level: int, _lo: int, _hi: int) -> bool:
        return level == self._depth

    def _exit(self, point: _Point, context: _Point) -> _Point:
        # Past the leaf, away from its router: nodes touching connect nothing.
        return (point[0], 2 * point[1] - context[1])

    def _router(self, point: _Point, _context: _Point) -> _Point:
        return (2 - point[0], point[1])

    def _router_glyph(self, level: int, lo: int) -> str:
        return "⬒" if self._same(level, lo) else "◒"

    def _same(self, level: int, lo: int) -> bool:
        index = lo >> (self._depth - level)
        return self._ids[level + 1][2 * index] == self._ids[level + 1][2 * index + 1]

    def _leaf_axis(self, _context: _Point) -> Literal["horizontal", "vertical"]:
        return "vertical"

    def _trunk_axis(self, _context: _Point) -> Literal["horizontal", "vertical"]:
        return "horizontal"

    def _children(self, level: int, lo: int, hi: int, router: _Point) -> list[_Child]:
        same = self._same(level, lo)
        half = (lo + hi) // 2
        # The root's wider separation leaves its startup and wires clear of
        # leaf outputs. Another level would overlap an ancestor's wire.
        if level != 0:
            pitch = 2
        elif self._depth == 2:
            pitch = 8
        else:
            pitch = 4
        pairs = ((-1, lo, half),) if same else ((-1, lo, half), (1, half, hi))
        return [
            (child_lo, child_hi, (router[0], router[1] + sign * pitch), router)
            for sign, child_lo, child_hi in pairs
        ]


class _StripTree(_TreeEmitter):
    """The strip tree: exits two columns left, children pitched by span."""

    def __init__(self, builder: _Builder, table: str, depth: int) -> None:
        super().__init__(builder, table)
        self._depth = depth
        self._ids = subtree_ids(table) if depth else [[int(table[0])]]

    def _leaf(self, level: int, lo: int, hi: int) -> bool:
        return self._ids[level][lo // (hi - lo)] < 2

    def _router(self, point: _Point, _context: _Point) -> _Point:
        return (point[0] - 2, point[1])

    def _router_glyph(self, _level: int, _lo: int) -> str:
        return "◒"

    def _leaf_axis(self, _context: _Point) -> Literal["horizontal", "vertical"]:
        return "horizontal"

    def _trunk_axis(self, _context: _Point) -> Literal["horizontal", "vertical"]:
        return "horizontal"

    def _children(self, level: int, lo: int, hi: int, router: _Point) -> list[_Child]:
        mid = (lo + hi) // 2
        return [
            (
                child_lo,
                child_hi,
                (router[0], router[1] + sign * (1 << (self._depth - level))),
                router,
            )
            for sign, child_lo, child_hi in ((-1, lo, mid), (1, mid, hi))
        ]


class _LayoutTree(_TreeEmitter):
    """The laid-out tree: alternating axes, spans halving every two levels."""

    def __init__(
        self,
        builder: _Builder,
        table: str,
        ids: Sequence[Sequence[int]],
        depth: int,
        *,
        prune: bool = True,
        flat: bool = False,
    ) -> None:
        super().__init__(builder, table)
        self._ids = ids
        self._depth = depth
        self._prune = prune
        self._flat = flat
        self._axes = ((1, 0), (0, 1))

    def run(self, level: int, lo: int, hi: int, point: _Point, context: _Point) -> None:
        """Pop mixed leaf pairs directly into their identity or NOT output."""
        if hi - lo != 2 or self._table[lo] == self._table[lo + 1]:
            super().run(level, lo, hi, point, context)
            return
        builder = self._builder
        builder.node(point, "◧")
        end = self._exit(point, context)
        builder.connect(_path(point, end, self._leaf_axis(context)), "double")
        if self._table[lo] == "0":
            builder.node(end, "◇")
            return
        # Bend into the old positive-child footprint: a straight NOT exit
        # enlarged small diagrams. See [ablations.literal_leaf_pair].
        builder.node(end, "□")
        axis = self._axes[level % 2]
        output = (end[0] + 2 * axis[0], end[1] + 2 * axis[1])
        builder.node(output, "◇")
        builder.connect(_path(end, output, self._child_axis(level)), "double")

    def _span(self, level: int) -> int:
        # ``flat`` halves the vertical pitch: a 2:1 (columns:rows) block.
        vertical = not self._axes[level % 2][0]
        return (4 if self._flat and vertical else 8) * (
            1 << ((self._depth - level - 1) // 2)
        ) - 2

    def _leaf(self, level: int, lo: int, hi: int) -> bool:
        # A constant span is a leaf wherever it sits: what it has not
        # popped is left on the stack.
        return hi - lo == 1 or (
            self._prune and self._ids[level][lo >> (self._depth - level)] < 2
        )

    def _router(self, point: _Point, context: _Point) -> _Point:
        return (point[0] + 2 * context[0], point[1] + 2 * context[1])

    def _router_glyph(self, level: int, _lo: int) -> str:
        return "◑" if self._axes[level % 2][0] else "◒"

    def _leaf_axis(self, context: _Point) -> Literal["horizontal", "vertical"]:
        return _first_axis(context[0])

    def _trunk_axis(self, context: _Point) -> Literal["horizontal", "vertical"]:
        return _first_axis(context[0])

    def _child_axis(self, level: int) -> Literal["horizontal", "vertical"]:
        return _first_axis(self._axes[level % 2][0])

    def _children(self, level: int, lo: int, hi: int, router: _Point) -> list[_Child]:
        axis = self._axes[level % 2]
        mid = (lo + hi) // 2
        pairs = ((-1, lo, mid), (1, mid, hi))
        children: list[_Child] = []
        for sign, child_lo, child_hi in pairs:
            incoming = (sign * axis[0], sign * axis[1])
            child = (
                router[0] + self._span(level) * incoming[0],
                router[1] + self._span(level) * incoming[1],
            )
            children.append((child_lo, child_hi, child, incoming))
        return children


def _coalesce(program: str) -> str:
    """Contract repeated straight transit strips, retaining one wire cell."""
    rows = program.splitlines()
    width = max(map(len, rows))
    rows = [row.ljust(width) for row in rows]

    def strips(lines: list[str], alphabet: str) -> list[str]:
        kept: list[str] = []
        allowed = set(alphabet)
        for line in lines:
            if not (kept and line == kept[-1] and set(line) <= allowed):
                kept.append(line)
        return kept

    # Ordinary generated diagrams carry one pointer at a time: a data arrival
    # starts the next execution leg. Contracting transit cannot change a merge.
    # Native XOR has concurrent starts but no repeated transit strips.
    rows = strips(rows, " │║")
    columns = strips(["".join(row[x] for row in rows) for x in range(width)], " ─═")
    return "\n".join(
        "".join(column[y] for column in columns).rstrip() for y in range(len(rows))
    )


def _constant_diagram(n: int, bit: str, columns: int) -> str:
    """Fold one read/print chain into rows without adding transit cells."""
    builder = _Builder()
    glyphs = ["▣", *["◇"] * n, "■" if bit == "1" else "□", "◇"]
    points = []
    for i, glyph in enumerate(glyphs):
        row, col = divmod(i, columns)
        point = (2 * (columns - 1 - col if row % 2 else col), 2 * row)
        builder.node(point, glyph)
        points.append(point)
    for i, (left, right) in enumerate(pairwise(points)):
        builder.connect(
            _path(left, right, "horizontal"), "double" if i == n + 1 else "single"
        )
    return builder.render()


def thisthat(truth_table: str, width: int | None = None) -> str:
    """Return a diagram with identical straight transit strips coalesced.

    See ``[ablations.transit_strip_coalescing]`` for the executed corpus.
    """
    n = _validate_truth_table(truth_table)
    if (bit := constant_output(truth_table)) is not None:
        program = _constant_diagram(n, bit, n + 3)
        return (
            _rotate_tree(program)
            if width and 0 < width < grid_width(program)
            else program
        )
    return _coalesce(_diagram(truth_table, width, plan=_DiagramPlan(truth_table, n)))


class _DiagramPlan:
    """Share the input selection and drawn candidates across layouts."""

    def __init__(self, table: str, n: int) -> None:
        self.table = table
        self.n = n

    @cached_property
    def essential(self) -> list[int]:
        return essential_inputs(self.table, self.n)

    @cached_property
    def projected(self) -> str:
        return read_at(self.table, self.essential, self.n)

    @cached_property
    def flat(self) -> str:
        return _coalesce(_tree(self.table, flat=True, plan=self))

    @cached_property
    def plain(self) -> str:
        # The balanced pitch saves 7.12% of exhaustive n=3 commands.
        # See [ablations.default_flat].
        return min(_coalesce(_tree(self.table, plan=self)), self.flat, key=grid_rank)

    @cached_property
    def program(self) -> str:
        plain = self.plain
        shared = shared_tree(self.table, plan=self)
        if shared is not None:
            candidate, cycles = shared
            if _admit_shared(plain, candidate, cycles, self.n):
                return candidate
        return plain

    @cached_property
    def strip(self) -> str:
        return _strip_tree(self.table, plan=self)


def _diagram(
    truth_table: str, width: int | None = None, *, plan: _DiagramPlan | None = None
) -> str:
    """Return a linear-area tree or a bounded DAG with shared residuals.

    The DAG uses directed crossings within the O(T) area of the plain tree;
    `_admit_shared` guards admission.  Narrow small arities additionally
    compare folded strips and streaming trees.
    """
    if width is not None and 0 < width < 3 and truth_table == "0110":
        # Equal-length paths merge both input transfers on native XOR.
        # Top-to-bottom update order reads the first input first; the result
        # returns along the lower wire to its input node, which now prints.
        return "▣\n│\n◇\n║\n▦\n║\n◇\n│\n▣"
    if plan is None:
        plan = _DiagramPlan(truth_table, _validate_truth_table(truth_table))
    program = plan.program
    if width is None or width <= 0:
        return program
    plain, program = _coalesce(plan.plain), _coalesce(program)
    narrow_plain = _narrow_tree(truth_table, plain, width, plan=plan)
    if program == plain:
        return narrow_plain
    narrow_shared = _narrow_tree(truth_table, program, width, plan=plan)
    if grid_width(narrow_shared) <= max(width, grid_width(narrow_plain)) and (
        grid_area(narrow_shared) < grid_area(narrow_plain)
    ):
        return narrow_shared
    return narrow_plain


def _admit_shared(plain: str, shared: str, cycles: int, n: int) -> bool:
    """Whether the shared DAG replaces the plain tree: smaller, bounded run.

    The cycle bound is 32 * 2^(n/2) - 29 for even ``n`` and 48 * 2^(n//2) - 29
    for odd.  The coordinate widths (one pointer, same bistack cells) must not
    exceed the plain tree's.
    """
    bound = 32 * (1 << (n // 2)) - 29 if n % 2 == 0 else 48 * (1 << (n // 2)) - 29
    old_rows, old_cols = len(plain.splitlines()), grid_width(plain)
    rows, cols = len(shared.splitlines()), grid_width(shared)
    coordinates = (rows - 1).bit_length() + (cols - 1).bit_length()
    old_coordinates = (old_rows - 1).bit_length() + (old_cols - 1).bit_length()
    return (
        rows * cols < old_rows * old_cols
        and cycles <= bound
        and coordinates <= old_coordinates
    )


def _narrow_tree(
    truth_table: str, program: str, width: int, *, plan: _DiagramPlan | None = None
) -> str:
    """Compare rotation, strip and tiny streaming forms of one candidate."""
    lines = program.splitlines()
    span = max(map(len, lines))
    if span <= width:
        return program
    if len(lines) < span:
        program = _rotate_tree(program)
    if grid_width(program) <= width:
        return program
    # A strip needs O(T log T) wires in general; bounding it at three inputs
    # keeps this fallback and the larger linear-area trees uniformly O(T).
    # Counted on the kept inputs: an ignored input only lengthens the loader.
    if plan is None:
        plan = _DiagramPlan(truth_table, _validate_truth_table(truth_table))
    if len(plan.essential) <= 3:
        program = narrowest_grid(program, plan.strip)
    if len(truth_table) <= 4 and grid_width(program) > width:
        streamed = _stream_tree(truth_table)
        return narrowest_grid(program, streamed)
    return program


def _stream_tree(table: str) -> str:
    """Read at most two inputs; equal halves discard onto the column stack."""
    depth = _validate_truth_table(table)
    ids = subtree_ids(table)
    builder = _Builder()
    _StreamTree(builder, table, ids, depth).run(0, 0, len(table), (0, 0), (0, 1))
    builder.node((1, 1), "▣")
    builder.connect([(1, 1), (0, 1), (0, 0)], "single")
    return builder.render()


def _rotate_tree(program: str) -> str:
    lines = program.splitlines()
    span = max(map(len, lines))
    # Rotate physical ports and router directions; bistack operations name
    # logical memory axes, independent of the diagram's orientation.
    directions = {"E": "N", "N": "W", "W": "S", "S": "E"}
    glyphs = dict(zip("◐◑◒◓", "◒◓◑◐", strict=True))
    glyphs.update(zip("▲▶▼◀", "◀▲▶▼", strict=True))
    glyphs.update(zip("△▷▽◁", "◁△▷▽", strict=True))
    for alphabet in (_SINGLE, _DOUBLE):
        glyphs.update(
            {
                glyph: alphabet[frozenset(directions[p] for p in ports)]
                for ports, glyph in alphabet.items()
            }
        )
    rows: list[dict[int, str]] = [{} for _ in range(span)]
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            if char != " ":
                rows[span - x - 1][y] = glyphs.get(char, char)
    return "\n".join(
        "".join(row.get(x, " ") for x in range(max(row, default=-1) + 1))
        for row in rows
    )


def _strip_tree(truth_table: str, *, plan: _DiagramPlan | None = None) -> str:
    """Build a small-arity vertical decision strip with channel-separated nodes."""
    if plan is None:
        plan = _DiagramPlan(truth_table, _validate_truth_table(truth_table))
    n, essential, table = plan.n, plan.essential, plan.projected
    depth = len(essential)
    builder = _Builder()
    _StripTree(builder, table, depth).run(0, 0, len(table), (0, 0), (0, 0))
    min_y = min(y for _, y in builder.cells())
    start = (0, min_y - 2 * n - 2 * len(essential) - 2)
    builder.node(start, "▣")
    previous = start
    for i in range(n):
        read = (0, previous[1] + 2)
        builder.node(read, "◇")
        builder.connect(_path(previous, read, "vertical"), "single")
        previous = read
        if i in essential:
            push = (0, read[1] + 2)
            builder.node(push, "◨")
            builder.connect(_path(read, push, "vertical"), "double")
            previous = push
    builder.connect(_path(previous, (0, 0), "vertical"), "single")
    return builder.render()


def _tree(
    truth_table: str,
    *,
    prune: bool = True,
    flat: bool = False,
    plan: _DiagramPlan | None = None,
) -> str:
    """Build the tree; ``prune=False`` keeps every input and unfolds spans.

    ``flat`` halves the vertical spans (twice as wide as tall).

    Ignored inputs are read and dropped.  Kept inputs are tested in input
    order at every node; the root's arms are not swapped.
    """
    if plan is None:
        plan = _DiagramPlan(truth_table, _validate_truth_table(truth_table))
    n = plan.n
    essential = plan.essential if prune else list(range(n))
    if len(essential) < n:
        truth_table = plan.projected
    return _layout(truth_table, n, essential, prune=prune, flat=flat)


def _layout(
    truth_table: str,
    n: int,
    essential: list[int],
    *,
    prune: bool = True,
    flat: bool = False,
) -> str:
    """Lay out the tree over ``truth_table``, whose level ``k`` pops input ``k``."""
    # No essential input: the table is one constant char, which subtree_ids
    # (table length 2**n) is not asked about.
    ids = subtree_ids(truth_table) if essential else [[int(truth_table[0])]]
    depth = len(essential)
    builder = _Builder()
    root = (0, 0)
    _LayoutTree(builder, truth_table, ids, depth, prune=prune, flat=flat).run(
        0, 0, len(truth_table), root, (0, 1)
    )
    cells = builder.cells()
    min_x = min(x for x, _ in cells)
    min_y = min(y for _, y in cells)
    loader_y = min_y - 2
    # An ignored input's read sends its bit nowhere and goes straight on.
    start_x = min(min_x, root[0] - 2 * n - 2 * len(essential) - 2)
    previous = _draw_loader(builder, (start_x, loader_y), n, essential)
    entry = (root[0], root[1] - 1)
    route = _path(previous, (root[0], loader_y), "horizontal")
    route += _path((root[0], loader_y), entry, "vertical")[1:]
    route.append(root)
    builder.connect(route, "single")
    return builder.render()


def _balance(truth_table: str, default: str | None = None) -> str:
    """Compare the default, the narrowest grid and the flat tree.

    The flat tree halves the vertical pitch, so even arities (square
    otherwise, side 2 x rows) become 2:1; odd arities already were.

    The inline tree and the square-width rewraps of both orientations never
    won (n=1..8, incl. tiled and constant-leaf tables); neither did walking
    down one column at a time (127 tables through n=11).
    """
    n = _validate_truth_table(truth_table)
    if (bit := constant_output(truth_table)) is not None:
        if default is None:
            default = _constant_diagram(n, bit, n + 3)
        return min(
            default,
            _constant_diagram(n, bit, isqrt(n + 2) + 1),
            key=balance_score,
        )
    plan = _DiagramPlan(truth_table, n)
    if default is None:
        default = _coalesce(plan.program)
    return min(
        default,
        _coalesce(_diagram(truth_table, 1, plan=plan)),
        plan.flat,
        key=balance_score,
    )


def shared_tree(
    table: str, *, plan: _DiagramPlan | None = None
) -> tuple[str, int] | None:
    """Return a shared grid and maximum cycles within the previous area envelope."""
    if plan is None:
        plan = _DiagramPlan(table, _validate_truth_table(table))
    n, ess = plan.n, plan.essential
    limit = max(_MIN_NODE_BUDGET, 2 * isqrt(len(table)))
    if not ess:
        return None
    return _draw_shared(plan.projected, n, ess, limit)


def thisthat_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    if request.balance:
        return _balance(request.table)
    return thisthat(request.table, request.width)
