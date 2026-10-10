"""thisthat boolean generator: a bistack-routed planar decision tree."""

from itertools import pairwise
from typing import Literal

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    _validate_truth_table,
    grid_width,
    narrowest_grid,
    read_at,
    subtree_ids,
)
from esolangs.tools.wrap import balance_score

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

    The DAG uses directed crossings within the preceding O(T) area envelope.
    The old grid,
    cycle bound and coordinate widths guard admission; narrow small arities
    additionally compare folded strips and streaming trees.
    """
    if width is not None and 0 < width < 3 and truth_table == "0110":
        # Equal-length paths merge both input transfers on native XOR.
        # Top-to-bottom update order reads the first input first; the result
        # returns along the lower wire to its input node, which now prints.
        return "▣\n│\n◇\n║\n▦\n║\n◇\n│\n▣"
    program = _tree(truth_table)
    plain = program
    from esolangs.tools.thisthat_shared import shared_tree

    shared = shared_tree(truth_table)
    if shared is not None:
        candidate, cycles = shared
        n = _validate_truth_table(truth_table)
        bound = 32 * (1 << (n // 2)) - 29 if n % 2 == 0 else 48 * (1 << (n // 2)) - 29
        old_rows, old_cols = len(program.splitlines()), grid_width(program)
        rows, cols = len(candidate.splitlines()), grid_width(candidate)
        # One pointer and the same bistack cells: keeping the sum of coordinate
        # widths no larger preserves the existing written-state bound.
        coordinates = (rows - 1).bit_length() + (cols - 1).bit_length()
        old_coordinates = (old_rows - 1).bit_length() + (old_cols - 1).bit_length()
        if (
            rows * cols < old_rows * old_cols
            and cycles <= bound
            and coordinates <= old_coordinates
        ):
            program = candidate
    if width is None or width <= 0:
        return program
    old = _narrow_tree(truth_table, plain, width)
    if program == plain:
        return old
    candidate = _narrow_tree(truth_table, program, width)
    old_area = len(old.splitlines()) * grid_width(old)
    area = len(candidate.splitlines()) * grid_width(candidate)
    if grid_width(candidate) <= max(width, grid_width(old)) and area < old_area:
        return candidate
    return old


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
    order (a greedy order saves 0.2% at n=8, under the 10% bar); the root's arms
    are not swapped (swapping saves 0.5% at n=8, under the 10% bar).
    """
    n = _validate_truth_table(truth_table)
    essential = _essential(subtree_ids(truth_table), n) if prune else list(range(n))
    if len(essential) < n:
        truth_table = read_at(truth_table, essential, n)
    order = tuple(range(len(essential)))
    if not (prune and essential):
        return _layout(truth_table, n, essential, order, prune=prune)
    return _layout(truth_table, n, essential, order)


def _layout(
    truth_table: str,
    n: int,
    essential: list[int],
    order: tuple[int, ...],
    *,
    prune: bool = True,
) -> str:
    """Lay out the tree over ``truth_table``, whose level ``k`` pops ``order[k]``.

    ``""`` when the row cannot pop them in that order.
    """
    plan = _deque_plan(order) if order else ([], [])
    if plan is None:
        return ""
    head_push, head_pop = plan
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
        builder.node(pop, "◧" if head_pop[level] else "◨")
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
    builder.node((start_x, loader_y), "▣")
    previous = (start_x, loader_y)
    for i in range(n):
        diamond = (previous[0] + 2, loader_y)
        builder.node(diamond, "◇")
        builder.connect(_path(previous, diamond, "horizontal"), "single")
        previous = diamond
        if i in essential:
            push = (diamond[0] + 2, loader_y)
            builder.node(push, "◧" if head_push[essential.index(i)] else "◨")
            builder.connect(_path(diamond, push, "horizontal"), "double")
            previous = push
    entry = (root[0], root[1] - 1)
    route = _path(previous, (root[0], loader_y), "horizontal")
    route += _path((root[0], loader_y), entry, "vertical")[1:]
    route.append(root)
    builder.connect(route, "single")
    return builder.render()


def _balance(truth_table: str, default: str) -> str:
    """Compare shared and inline tree orientations with narrow fallbacks."""
    candidates = [default, _tree(truth_table)]
    for base, shared in ((default, True), (candidates[1], False)):
        previous = base
        for _ in range(3):
            width = max(1, grid_width(previous) - 1)
            previous = (
                thisthat(truth_table, width)
                if shared
                else _narrow_tree(truth_table, base, width)
            )
            candidates.append(previous)
    candidates.append(thisthat(truth_table, 1))
    return min(candidates, key=balance_score)


def _deque_plan(order: tuple[int, ...]) -> tuple[list[bool], list[bool]] | None:
    """Return head pushes by input and head pops by level that pop ``order``.

    Inputs are read in order and each goes to the row's head or tail, so
    the row reads (head first) the head-pushed inputs descending, input 0,
    then the tail-pushed ones ascending; the tree pops either end at each
    level.  Before input 0 is popped each pop is the largest left on its
    side, so that prefix splits into two descending runs, the tail run
    above every input popped after 0; those are all tail-pushed, so they
    leave the row as a run each pop takes the least or the greatest of.
    ``None`` when ``order`` has no such split: the plan is the greedy fit
    (a tie goes to the lower run), which finds every poppable order.
    """
    depth = len(order)
    zero = order.index(0)
    floor = max(order[zero + 1 :], default=-1)
    head_push = [False] * depth
    head_pop = []
    last = {True: depth, False: depth}
    for x in order[:zero]:
        fits = [
            head for head in (True, False) if x < last[head] and (head or x > floor)
        ]
        if not fits:
            return None
        head = min(fits, key=last.__getitem__)
        last[head] = x
        head_push[x] = head
        head_pop.append(head)
    head_pop.append(True)
    rest = sorted(order[zero + 1 :])
    for x in order[zero + 1 :]:
        if x not in (rest[0], rest[-1]):
            return None
        head_pop.append(x == rest[0])
        rest.remove(x)
    return head_push, head_pop


LANGUAGE = Language(
    "thisthat",
    "grid_based.thisthat",
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
