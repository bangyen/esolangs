"""thisthat Boolean program generator: a bistack-routed planar decision tree.

A loader reads each input and pushes essential bits to the bistack; each node
pops one and routes by a ``◒``/``◑`` router, ignored inputs only read, and a
node with equal halves pops its bit onto the column stack and takes one half.
A bounded DAG replaces the tree when smaller; narrow widths try rotation,
strips and streaming trees.

Size:
    Linear area in T for the plain tree; n=8 parity: 6,379 chars, n=10 and:
    113,005 chars, n=10 random 1847: 238,413 chars.

Decisions:
    Greedy input order saves 0.2% at n=8 and swapping the root's arms 0.5%,
    both under the 10% bar.
"""

from collections import defaultdict
from itertools import pairwise
from math import isqrt
from typing import Literal, NamedTuple

from esolangs.generation.helpers import (
    _validate_truth_table,
    grid_area,
    grid_width,
    narrowest_grid,
    read_at,
    subtree_ids,
)
from esolangs.generation.wrap import balance_score
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

_STEP = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}
_OPPOSITE = {"E": "W", "W": "E", "N": "S", "S": "N"}
_PORTS = [
    frozenset(ports)
    for ports in (
        "EW",
        "NS",
        "ES",
        "WS",
        "EN",
        "WN",
        "ENS",
        "WNS",
        "EWS",
        "EWN",
        "EWNS",
    )
]
_SINGLE = dict(zip(_PORTS, "─│┌┐└┘├┤┬┴┼", strict=True))
_DOUBLE = dict(zip(_PORTS, "═║╔╗╚╝╠╣╦╩╬", strict=True))
_NAME = {step: name for name, step in _STEP.items()}


def _path(
    start: tuple[int, int],
    end: tuple[int, int],
    first_axis: Literal["horizontal", "vertical"],
) -> list[tuple[int, int]]:
    x, y = start
    points = [(x, y)]
    axes: tuple[tuple[int, int], ...] = ((0, end[0]), (1, end[1]))
    if first_axis == "vertical":
        axes = tuple(reversed(axes))
    for axis, target in axes:
        while (x, y)[axis] != target:
            if axis == 0:
                x += 1 if target > x else -1
            else:
                y += 1 if target > y else -1
            points.append((x, y))
    return points


def _first_axis(horizontal: int) -> Literal["horizontal", "vertical"]:
    return "horizontal" if horizontal else "vertical"


class _Builder:
    def __init__(self) -> None:
        self.nodes: dict[tuple[int, int], str] = {}
        self.wires: dict[tuple[int, int], tuple[str, set[str]]] = {}

    def node(self, point: tuple[int, int], glyph: str) -> None:
        if point in self.nodes:
            raise ValueError("thisthat layout collision")
        self.wires.pop(point, None)
        self.nodes[point] = glyph

    def connect(self, points: list[tuple[int, int]], kind: str) -> None:
        for left, right in pairwise(points):
            delta = (right[0] - left[0], right[1] - left[1])
            direction = _NAME[delta]
            for point, port in ((left, direction), (right, _OPPOSITE[direction])):
                if point in self.nodes:
                    continue
                old_kind, ports = self.wires.setdefault(point, (kind, set()))
                if old_kind != kind:
                    raise ValueError("thisthat wire collision")
                ports.add(port)

    def cells(self) -> set[tuple[int, int]]:
        return set(self.nodes) | set(self.wires)

    def render(self) -> str:
        cells = self.cells()
        min_x = min(x for x, _ in cells)
        min_y = min(y for _, y in cells)
        width = max(x for x, _ in cells) - min_x + 1
        height = max(y for _, y in cells) - min_y + 1
        rows = [[" "] * width for _ in range(height)]
        for (x, y), glyph in self.nodes.items():
            rows[y - min_y][x - min_x] = glyph
        for (x, y), (kind, ports) in self.wires.items():
            glyphs = _SINGLE if kind == "single" else _DOUBLE
            rows[y - min_y][x - min_x] = glyphs[frozenset(ports)]
        return "\n".join("".join(row).rstrip() for row in rows)


def thisthat(truth_table: str, width: int | None = None) -> str:
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
    plain = _tree(truth_table)
    program = plain

    shared = shared_tree(truth_table)
    if shared is not None:
        candidate, cycles = shared
        if _admit_shared(plain, candidate, cycles, _validate_truth_table(truth_table)):
            program = candidate
    if width is None or width <= 0:
        return program
    narrow_plain = _narrow_tree(truth_table, plain, width)
    if program == plain:
        return narrow_plain
    narrow_shared = _narrow_tree(truth_table, program, width)
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


def _narrow_tree(truth_table: str, program: str, width: int) -> str:
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
    n = _validate_truth_table(truth_table)
    if len(_essential(subtree_ids(truth_table), n)) <= 3:
        narrow = _strip_tree(truth_table)
        program = narrowest_grid(program, narrow)
    if len(truth_table) <= 4 and grid_width(program) > width:
        streamed = _stream_tree(truth_table)
        return narrowest_grid(program, streamed)
    return program


def _stream_tree(table: str) -> str:
    """Read at most two inputs; equal halves discard onto the column stack."""
    depth = _validate_truth_table(table)
    ids = subtree_ids(table)
    builder = _Builder()

    def tree(
        level: int, lo: int, hi: int, point: tuple[int, int], parent: tuple[int, int]
    ) -> None:
        if level == depth:
            builder.node(point, "■" if table[lo] == "1" else "□")
            # Past the leaf, away from its router: nodes touching connect nothing.
            output = (point[0], 2 * point[1] - parent[1])
            builder.node(output, "◇")
            builder.connect(_path(point, output, "vertical"), "double")
            return
        router = (2 - point[0], point[1])
        builder.node(point, "◇")
        index = lo >> (depth - level)
        same = ids[level + 1][2 * index] == ids[level + 1][2 * index + 1]
        builder.node(router, "⬒" if same else "◒")
        builder.connect(_path(point, router, "horizontal"), "double")
        half = (lo + hi) // 2
        # The root's wider separation leaves its startup and wires clear of
        # leaf outputs. Another level would overlap an ancestor's wire.
        if level != 0:
            pitch = 2
        elif depth == 2:
            pitch = 8
        else:
            pitch = 4
        children = ((-1, lo, half),) if same else ((-1, lo, half), (1, half, hi))
        for sign, start, end in children:
            child = (router[0], router[1] + sign * pitch)
            builder.connect(_path(router, child, "vertical"), "single")
            tree(level + 1, start, end, child, router)

    tree(0, 0, len(table), (0, 0), (0, 1))
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


def _essential(ids: list[list[int]], n: int) -> list[int]:
    """Return the inputs on whose level some node has unequal halves."""
    return [i for i in range(n) if ids[i + 1][::2] != ids[i + 1][1::2]]


def _strip_tree(truth_table: str) -> str:
    """Build a small-arity vertical decision strip with channel-separated nodes."""
    n = _validate_truth_table(truth_table)
    essential = _essential(subtree_ids(truth_table), n)
    table = read_at(truth_table, essential, n)
    depth = len(essential)
    builder = _Builder()

    def tree(level: int, lo: int, hi: int, pop: tuple[int, int]) -> None:
        output = (pop[0] - 2, pop[1])
        if all(bit == table[lo] for bit in table[lo:hi]):
            builder.node(pop, "■" if table[lo] == "1" else "□")
            builder.node(output, "◇")
            builder.connect(_path(pop, output, "horizontal"), "double")
            return
        builder.node(pop, "◧")
        builder.node(output, "◒")
        builder.connect(_path(pop, output, "horizontal"), "double")
        mid = (lo + hi) // 2
        for sign, child_lo, child_hi in ((-1, lo, mid), (1, mid, hi)):
            child = (output[0], output[1] + sign * (1 << (depth - level)))
            builder.connect(_path(output, child, "vertical"), "single")
            tree(level + 1, child_lo, child_hi, child)

    tree(0, 0, len(table), (0, 0))
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


def _tree(truth_table: str, *, prune: bool = True) -> str:
    """Build the tree; ``prune=False`` tests every input at every node.

    Ignored inputs are read and dropped.  A node whose halves agree pops its
    bit onto the unpopped column stack.  Kept inputs are tested in input
    order; the root's arms are not swapped.
    """
    n = _validate_truth_table(truth_table)
    essential = _essential(subtree_ids(truth_table), n) if prune else list(range(n))
    if len(essential) < n:
        truth_table = read_at(truth_table, essential, n)
    return _layout(truth_table, n, essential, prune=prune)


def _layout(
    truth_table: str,
    n: int,
    essential: list[int],
    *,
    prune: bool = True,
) -> str:
    """Lay out the tree over ``truth_table``, whose level ``k`` pops input ``k``."""
    # No essential input: the table is one constant char, which subtree_ids
    # (table length 2**n) is not asked about.
    ids = subtree_ids(truth_table) if essential else [[int(truth_table[0])]]
    depth = len(essential)
    builder = _Builder()
    axes = ((1, 0), (0, 1))

    def span(level: int) -> int:
        return 8 * (1 << ((depth - level - 1) // 2)) - 2

    def tree(
        level: int,
        lo: int,
        hi: int,
        pop: tuple[int, int],
        incoming: tuple[int, int],
    ) -> None:
        index = lo >> (depth - level)
        if hi - lo == 1 or (prune and ids[level][index] < 2):
            # A constant span is a leaf wherever it sits: what it has not
            # popped is left on the stack.
            builder.node(pop, "■" if truth_table[lo] == "1" else "□")
            output = (pop[0] + 2 * incoming[0], pop[1] + 2 * incoming[1])
            builder.node(output, "◇")
            builder.connect(_path(pop, output, _first_axis(incoming[0])), "double")
            return
        builder.node(pop, "◧")
        router = (pop[0] + 2 * incoming[0], pop[1] + 2 * incoming[1])
        axis = axes[level % 2]
        mid = (lo + hi) // 2
        children: tuple[tuple[int, int, int], ...] = (
            (-1, lo, mid),
            (1, mid, hi),
        )
        if prune and ids[level + 1][2 * index] == ids[level + 1][2 * index + 1]:
            # The halves agree: pop the bit onto the column stack, which
            # nothing pops, and go on into the one half both values share.
            # Row 0 and column 0 share cell (0, 0); the push lands there only
            # when the row is empty, and then the half is a leaf.  A loader
            # discard could land there before the row fills, so it has none.
            builder.node(router, "⬒")
            children = children[:1]
        else:
            builder.node(router, "◑" if axis[0] else "◒")
        builder.connect(_path(pop, router, _first_axis(incoming[0])), "double")
        for sign, child_lo, child_hi in children:
            child_incoming = (sign * axis[0], sign * axis[1])
            child = (
                router[0] + span(level) * child_incoming[0],
                router[1] + span(level) * child_incoming[1],
            )
            builder.connect(_path(router, child, _first_axis(axis[0])), "single")
            tree(level + 1, child_lo, child_hi, child, child_incoming)

    root = (0, 0)
    tree(0, 0, len(truth_table), root, (0, 1))
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


def _balance(truth_table: str, default: str) -> str:
    """Compare shared and inline tree orientations at the square width and at 1.

    Each is rewrapped to the side of the square holding its area; width 1 is
    the narrowest grid.  Walking down one column at a time (``width - 1``,
    three times) never beat these on 127 tables through n=11.
    """
    inline = _tree(truth_table)
    candidates = [default, inline, thisthat(truth_table, 1)]
    for base, shared in ((default, True), (inline, False)):
        width = max(1, isqrt(grid_area(base)))
        candidates.append(
            thisthat(truth_table, width)
            if shared
            else _narrow_tree(truth_table, base, width)
        )
    return min(candidates, key=balance_score)


_MIN_NODE_BUDGET = 8


class _Dag(NamedTuple):
    layers: list[list[tuple[int, int]]]
    children: dict[tuple[int, int], list[tuple[int, int]]]
    terminal: set[tuple[int, int]]
    incoming: dict[tuple[int, int], int]


def _build_dag(ids: list[list[int]], m: int) -> _Dag:
    """Return the shared-subtree DAG."""
    representatives = {(0, ids[0][0]): 0}
    pending = [[(0, ids[0][0])]] + [[] for _ in range(m - 1)]
    layers = []
    incoming: dict[tuple[int, int], int] = defaultdict(int)
    children = {}
    terminal = set()
    for level in range(m):
        layer = pending[level]
        layers.append(layer)
        for key in layer:
            lo = representatives[key]
            span = 1 << (m - level)
            idx = lo // span
            zero_id, one_id = ids[level + 1][2 * idx : 2 * idx + 2]
            kids = []
            for side, (state, row) in enumerate(
                ((zero_id, lo), (one_id, lo + span // 2))
            ):
                child = (-1, state) if state < 2 else (level + 1, state)
                if child[0] < 0:
                    terminal.add(child)
                else:
                    if child not in representatives:
                        representatives[child] = row
                        pending[level + 1].append(child)
                if side == 0 or zero_id != one_id:
                    incoming[child] += 1
                kids.append(child)
            children[key] = kids
    return _Dag(layers, children, terminal, incoming)


def _draw_nodes(
    builder: _Builder,
    nodes: list[tuple[int, int]],
    ys: dict[tuple[int, int], int],
    columns: dict[tuple[int, int], int],
    children: dict[tuple[int, int], list[tuple[int, int]]],
) -> tuple[dict[tuple[int, int], int], dict[int, dict[int, int]]]:
    """Draw every node and its outgoing wires; return (costs, bus events)."""
    # Two column banks alternate with depth. A bank's old edges end before
    # its next parents begin; constants retain their own two downward buses.
    costs: dict[tuple[int, int], int] = {}
    buses: dict[int, dict[int, int]] = {}
    for key in reversed(nodes):
        y = ys[key]
        entry = (0, y - 4)
        point = (0, y)
        router = (2, y)
        bus = columns[key]
        builder.node(entry, "▼")
        builder.node((bus, y - 4), "◀")
        builder.connect(_path((bus, y - 4), entry, "horizontal"), "single")
        builder.connect(_path(entry, point, "vertical"), "single")
        if key[0] < 0:
            builder.node(point, "■" if key[1] else "□")
            builder.node(router, "◇")
            costs[key] = 7
        else:
            builder.node(point, "◧")
            zero, one = children[key]
            builder.node(router, "⬒" if zero == one else "◒")
            edges = [(1, one)] if zero == one else [(-1, zero), (1, one)]
            steps = []
            for sign, child in edges:
                row = y + 2 * sign
                col = columns[child]
                target_y = ys[child] - 4
                builder.node((col, row), "▼")
                builder.connect(_path(router, (2, row), "vertical"), "single")
                builder.connect(_path((2, row), (col, row), "horizontal"), "single")
                events = buses.setdefault(col, {})
                events[row] = events.get(row, 0) + 1
                events[target_y] = events.get(target_y, 0) - 1
                steps.append(6 + 2 * col + target_y - row + costs[child])
            costs[key] = max(steps)
        builder.connect(_path(point, router, "horizontal"), "double")
    return costs, buses


def _draw_buses(builder: _Builder, buses: dict[int, dict[int, int]]) -> None:
    """Draw each bus column as its merged runs of overlapping edges."""
    # Merge overlapping bus edges before drawing: independently tracing every
    # route to a terminal costs N² on a narrow N-node DAG. Each bus is scanned
    # once within the admitted rectangle, keeping construction O(T).
    for col, events in buses.items():
        active = 0
        begin = None
        for row in range(min(events), max(events) + 1):
            active += events.get(row, 0)
            if active and begin is None:
                begin = row
            elif not active and begin is not None:
                builder.connect(_path((col, begin), (col, row), "vertical"), "single")
                begin = None


def _hollow_crossings(builder: _Builder) -> None:
    """Turn four-way single-wire crossings into hollow arrows."""
    # Hollow downward arrows pass horizontal traffic straight through while
    # keeping vertical traffic downward; solid arrows merge at destinations.
    for point, (kind, ports) in list(builder.wires.items()):
        if kind == "single" and ports == set("EWNS"):
            builder.node(point, "▽")


def _draw_loader(
    builder: _Builder,
    start: tuple[int, int],
    n: int,
    essential: list[int],
) -> tuple[int, int]:
    """Draw the start node and one read per input, rightward; return the end.

    An essential input's read is followed by its tail push (◨); an ignored
    input's read sends its bit nowhere and goes straight on.
    """
    builder.node(start, "▣")
    previous = start
    for i in range(n):
        diamond = (previous[0] + 2, start[1])
        builder.node(diamond, "◇")
        builder.connect(_path(previous, diamond, "horizontal"), "single")
        previous = diamond
        if i in essential:
            pushed = (diamond[0] + 2, start[1])
            builder.node(pushed, "◨")
            builder.connect(_path(diamond, pushed, "horizontal"), "double")
            previous = pushed
    return previous


def _draw_input_chain(builder: _Builder, n: int, m: int, ess: list[int]) -> None:
    """Draw the input-reading chain feeding the root entry."""
    previous = _draw_loader(builder, (-(2 * n + 2 * m + 2), -6), n, ess)
    builder.connect(
        _path(previous, (0, -6), "horizontal")
        + _path((0, -6), (0, -4), "vertical")[1:],
        "single",
    )


def shared_tree(table: str) -> tuple[str, int] | None:
    """Return a shared grid and maximum cycles within the previous area envelope."""
    n = _validate_truth_table(table)
    limit = max(_MIN_NODE_BUDGET, 2 * isqrt(len(table)))
    ess = _essential(subtree_ids(table), n)
    if not ess:
        return None
    table = read_at(table, ess, n)
    m = len(ess)
    layers, children, terminal, incoming = _build_dag(subtree_ids(table), m)
    if not any(key[0] >= 0 and count > 1 for key, count in incoming.items()):
        return None
    nodes = [key for layer in layers for key in layer] + sorted(terminal)
    banks = [
        max((len(layer) for layer in layers[parity::2]), default=0) for parity in (0, 1)
    ]
    # The former node cap bounded both dimensions independently. Price their
    # product instead, admitting long narrow DAGs within the same O(T) envelope.
    count = len(nodes)
    width = 2 * sum(banks) + 2 * n + 2 * m + 9
    height = 8 * count - 1
    if width * height > (4 * limit + 4 * n + 9) * (8 * limit - 1):
        return None
    slots = {key: slot for layer in layers for slot, key in enumerate(layer)}
    columns = {
        key: 4 + 2 * key[1]
        if key[0] < 0
        else 8 + 2 * (slots[key] + banks[0] * (key[0] % 2))
        for key in nodes
    }
    ys = {key: 8 * i for i, key in enumerate(nodes)}
    builder = _Builder()
    costs, buses = _draw_nodes(builder, nodes, ys, columns, children)
    _draw_buses(builder, buses)
    _hollow_crossings(builder)
    _draw_input_chain(builder, n, m, ess)
    return builder.render(), 2 * n + 2 * m + 4 + costs[nodes[0]]


LANGUAGE = Language(
    "thisthat",
    "thisthat",
    category="grid_based",
    random=True,
    boolean=thisthat,
    split=True,
    contract=BooleanContract(
        input_shape="char_stream",
        ignores_whitespace=True,
        input_sets=True,
    ),
    balance=_balance,
    no_wrap="the H-tree's nodes and wires occupy fixed grid coordinates",
    eof="an exhausted '◇' sends the spec's empty transfer",
    empty_program="thisthat needs at least one start node",
)
