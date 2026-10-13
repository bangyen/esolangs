"""Layered residual stems with first-arrival ownership and interior joins."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace

from esolangs.generation.helpers import (
    _residual_ids,
    _validate_truth_table,
    essential_inputs,
    permute_truth_table,
    read_at,
)

from .render import (
    _UNIT,
    Node,
    _Cursor,
    chain,
    chain_onto,
    correction,
    loader_reads,
)
from .shared import CanvasPlan, stroke_plan

type State = tuple[int, int]
type Edge = tuple[int, int, int]


class _StemCursor(_Cursor):
    def advance(self, direction: tuple[int, int], steps: int = 1) -> None:
        if steps < 0:
            raise ValueError("forward route runs backward")
        self.y += direction[0] * steps
        self.x += direction[1] * steps
        if steps:
            self._current.append((self.y, self.x))
        self.heading = direction


def _join_lanes(spans: list[tuple[Edge, int, int]]) -> tuple[dict[Edge, int], int]:
    """Allocate disjoint padded spans by left edge in O(edges + width) work."""
    if not spans:
        return {}, 0
    starts: dict[int, list[tuple[Edge, int]]] = {}
    for edge, a, b in spans:
        # Padding keeps unrelated spans three units apart, including landings.
        lo, hi = min(a, b) - 1, max(a, b) + 1
        starts.setdefault(lo, []).append((edge, hi))
    ends: dict[int, list[int]] = {}
    available: deque[int] = deque()
    lanes: dict[Edge, int] = {}
    count = 0
    for x in range(min(starts), max(starts) + 1):
        available.extend(ends.pop(x, ()))
        for edge, hi in starts.get(x, ()):
            if available:
                lane = available.popleft()
            else:
                lane = count
                count += 1
            lanes[edge] = lane
            ends.setdefault(hi + 1, []).append(lane)
    return lanes, count


def _packed_join_lanes(
    arrivals: list[tuple[Edge, int, int]],
    joins: list[tuple[Edge, int, int]],
    arrival_lanes: dict[Edge, int],
    arrival_count: int,
    minimums: dict[Edge, int],
) -> tuple[dict[Edge, int], int]:
    """First-fit padded joins below their own arrival in shared lanes."""
    occupied: list[list[tuple[int, int]]] = [[] for _ in range(arrival_count)]
    for edge, a, b in arrivals:
        occupied[arrival_lanes[edge]].append((min(a, b) - 1, max(a, b) + 1))
    spans = sorted((min(a, b) - 1, max(a, b) + 1, edge) for edge, a, b in joins)
    lanes = {}
    for lo, hi, edge in spans:
        lane = minimums[edge]
        while lane < len(occupied) and any(
            not (hi < a or lo > b) for a, b in occupied[lane]
        ):
            lane += 1
        while lane >= len(occupied):
            occupied.append([])
        occupied[lane].append((lo, hi))
        lanes[edge] = lane
    return lanes, len(occupied)


@dataclass(frozen=True, slots=True)
class _CanvasOptions:
    """Layered-stem layout switches for :func:`_forward_canvas`."""

    destination_moves: bool = False
    streaming: bool = False
    centered: bool = False
    median_order: bool = False
    packed: bool = False
    projected: bool = False


# The seven canvases accumulate switches: each builds on the previous one,
# except projected streaming, which branches off centered streaming.
_FORWARD_OPTIONS = _CanvasOptions()
_DESTINATION_OPTIONS = replace(_FORWARD_OPTIONS, destination_moves=True)
_STREAMING_OPTIONS = replace(_DESTINATION_OPTIONS, streaming=True)
_CENTERED_STREAMING_OPTIONS = replace(_STREAMING_OPTIONS, centered=True)
_MEDIAN_STREAMING_OPTIONS = replace(_CENTERED_STREAMING_OPTIONS, median_order=True)
_PACKED_STREAMING_OPTIONS = replace(_MEDIAN_STREAMING_OPTIONS, packed=True)
_PROJECTED_STREAMING_OPTIONS = replace(_CENTERED_STREAMING_OPTIONS, projected=True)


def forward_canvas(
    table: str, old_area: int, *, unit: int = _UNIT
) -> tuple[Node, CanvasPlan] | None:
    """Return a smaller descending residual DAG with at most 5n commands."""
    return _forward_canvas(table, old_area, _FORWARD_OPTIONS, unit=unit)


def destination_canvas(
    table: str, old_area: int, *, unit: int = _UNIT
) -> tuple[Node, CanvasPlan] | None:
    """Share pointer moves on destination stems with separated narrow forks."""
    return _forward_canvas(table, old_area, _DESTINATION_OPTIONS, unit=unit)


def streaming_canvas(
    table: str, old_area: int, *, unit: int = _UNIT
) -> tuple[Node, CanvasPlan] | None:
    """Read in input order on shared stems, overwriting cell zero."""
    return _forward_canvas(table, old_area, _STREAMING_OPTIONS, unit=unit)


def centered_streaming_canvas(
    table: str, old_area: int, *, unit: int = _UNIT
) -> tuple[Node, CanvasPlan] | None:
    """Center streamed layers on eight-unit columns to shorten arrivals."""
    return _forward_canvas(table, old_area, _CENTERED_STREAMING_OPTIONS, unit=unit)


def median_streaming_canvas(
    table: str, old_area: int, *, unit: int = _UNIT
) -> tuple[Node, CanvasPlan] | None:
    """Order centered streamed layers by the lower median incoming rail."""
    return _forward_canvas(table, old_area, _MEDIAN_STREAMING_OPTIONS, unit=unit)


def packed_streaming_canvas(
    table: str, old_area: int, *, unit: int = _UNIT
) -> tuple[Node, CanvasPlan] | None:
    """Pack median-ordered arrivals and joins with per-stem precedence."""
    return _forward_canvas(table, old_area, _PACKED_STREAMING_OPTIONS, unit=unit)


def projected_streaming_canvas(
    table: str, old_area: int, *, unit: int = _UNIT
) -> tuple[Node, CanvasPlan] | None:
    """Share essential residuals while draining ignored reads on their stems."""
    return _forward_canvas(table, old_area, _PROJECTED_STREAMING_OPTIONS, unit=unit)


@dataclass(frozen=True, slots=True)
class _Dag:
    """Residual DAG over the kept inputs, plus the read counts between them."""

    original_n: int
    kept: list[int]
    children: dict[int, tuple[int, int]]
    constants: dict[int, int | None]
    levels: list[list[int]]

    @property
    def n(self) -> int:
        return len(self.kept)

    def reads_at(self, depth: int) -> str:
        if depth == self.n:
            return "i" * (self.original_n - self.kept[-1] - 1)
        return "i" * (self.kept[depth] - (self.kept[depth - 1] if depth else -1))

    def reader_height(self, depth: int) -> int:
        # Each native read advances six units; retain four before the fork.
        return 10 + 6 * (len(self.reads_at(depth)) - 1) if depth < self.n else 10

    def is_fork(self, residual: int) -> bool:
        return self.children[residual][0] != self.children[residual][1]


@dataclass(slots=True)
class _Layout:
    """Per-state fork and entry points and per-edge join points, in units."""

    gaps: dict[State, int]
    forks: dict[State, tuple[int, int]]
    entry: dict[State, tuple[int, int]]
    join: dict[Edge, tuple[int, int]]


def _load_dag(table: str, options: _CanvasOptions) -> _Dag | None:
    original_n = _validate_truth_table(table)
    full_read = options.streaming and not options.projected
    kept = list(range(original_n)) if full_read else essential_inputs(table, original_n)
    if options.projected and len(kept) == original_n:
        return None
    n = len(kept)
    if n < 2:
        return None
    reduced = table if full_read else read_at(table, kept, original_n)
    levels, children, constants = _residual_ids(
        reduced
        if options.streaming
        else permute_truth_table(reduced, tuple(range(n - 1, -1, -1))),
        n,
    )
    return _Dag(original_n, kept, children, constants, levels)


def _visit(
    dag: _Dag,
    options: _CanvasOptions,
    state: State,
    seen: set[State],
    first: dict[State, Edge],
    incoming: list[list[tuple[Edge, State]]],
) -> None:
    if state in seen:
        return
    seen.add(state)
    depth, residual = state
    if depth == dag.n:
        return
    arms = (0, 1) if dag.is_fork(residual) else (0,)
    for bit in arms:
        target = dag.children[residual][bit]
        if options.streaming or dag.constants[target] is None:
            edge = depth, residual, bit
            dest = depth + 1, target
            first.setdefault(dest, edge)
            incoming[depth + 1].append((edge, dest))
            _visit(dag, options, dest, seen, first, incoming)


def _stem_gaps(
    dag: _Dag, options: _CanvasOptions, members: list[list[int]]
) -> dict[State, int]:
    # Destination-mode columns are multiples of eight; outgoing rails are
    # 2 or 6 mod 8. This separates rails from nodes and the +/-1 opcode ink.
    # Gaps 2/8 with variable pitch failed native dense n=8 extraction;
    # 2/10 preserves the residue separation and executes every row.
    return {
        (depth, residual): (
            2
            if options.streaming
            or all(dag.constants[dag.children[residual][bit]] is None for bit in (0, 1))
            else 10
        )
        if options.destination_moves
        else 8
        for depth, level in enumerate(members)
        for residual in level
    }


def _rail(layout: _Layout, edge: Edge) -> int:
    """Column of the rail leaving an edge's source fork."""
    gap = layout.gaps[edge[:2]]
    return layout.forks[edge[0], edge[1]][1] + (-gap if edge[2] == 0 else gap)


def _median_order(
    layout: _Layout, incoming: list[tuple[Edge, State]], level: list[int]
) -> list[int]:
    """Order a level by the lower median incoming rail column."""
    parents: dict[int, list[int]] = {residual: [] for residual in level}
    for edge, dest in incoming:
        parents[dest[1]].append(_rail(layout, edge))

    ranked = []
    for residual, rails in parents.items():
        rails.sort()
        ranked.append((rails[(len(rails) - 1) // 2], residual))

    # One forward pass preserves eight-unit rail separation. Native
    # dense8 falls from 37,795,200 to 36,982,400 scale-one pixels.
    return [residual for _, residual in sorted(ranked)]


def _level_columns(
    options: _CanvasOptions, gaps: dict[State, int], depth: int, level: list[int]
) -> dict[int, int]:
    columns = {}
    column = 0
    previous_gap = gaps[depth, level[0]]
    for index, residual in enumerate(level):
        gap = gaps[depth, residual]
        if index:
            column += previous_gap + gap + 4 if options.destination_moves else 20
        columns[residual] = column
        previous_gap = gap
    if options.centered:
        # Eight-unit translation preserves node/rail residue separation.
        offset = -8 * (column // 16)
        columns = {residual: x + offset for residual, x in columns.items()}
    return columns


def _place_level(
    dag: _Dag,
    options: _CanvasOptions,
    layout: _Layout,
    incoming: list[tuple[Edge, State]],
    first: dict[State, Edge],
    depth: int,
    level: list[int],
    base: int,
) -> int:
    """Place one layer's forks, entries and joins; return the next base row."""
    forks, entry, join = layout.forks, layout.entry, layout.join
    if options.median_order and depth:
        level = _median_order(layout, incoming, level)
    extras = [(edge, dest) for edge, dest in incoming if first[dest] != edge]
    columns = _level_columns(options, layout.gaps, depth, level)
    join_spans = [
        (edge, _rail(layout, edge), columns[dest[1]]) for edge, dest in extras
    ]
    arrivals = (
        [
            (
                first[depth, residual],
                _rail(layout, first[depth, residual]),
                columns[residual],
            )
            for residual in level
        ]
        if depth
        else []
    )
    arrival_lanes, arrival_count = _join_lanes(arrivals)
    if depth == 0:
        arrival_count = 1
    if options.packed:
        # A join lands four units below its own arrival; unrelated
        # arrivals may reuse its row. Native dense8 saves 812,800 pixels.
        lanes, total = _packed_join_lanes(
            arrivals,
            join_spans,
            arrival_lanes,
            arrival_count,
            {edge: arrival_lanes[first[dest]] + 2 for edge, dest in extras},
        )
        lane_count = total - arrival_count
    else:
        lanes, lane_count = _join_lanes(join_spans)
    # Disjoint arrival/join spans reuse rows. At n=22 majority, scale 1,
    # this emits 87,270,400 pixels versus 123,110,400 (29.1%); both native
    # programs pass 37 rows with the same 98-command maximum.
    # In the original mode, all 81 adjacent arm-shape pairs at pitch 20 keep
    # opcode ink at least one unit apart (20px > the 15px star probe).
    # Entry/join lanes contain no opcodes and use two-unit spacing: at a
    # one-unit pitch a join's diagonal lands on the next lane's row even
    # with the own-arrival gap widened to four units, reading 0xFAC748EF
    # row 01010 as 1 not 0 (see tests/test_boolean_line_landing.py).
    for residual in level:
        state = depth, residual
        entry[state] = (
            base + 4 + 2 * (arrival_lanes[first[state]] if depth else 0),
            columns[residual],
        )
        forks[state] = (
            base
            + (20 if options.destination_moves else 16)
            + 2 * arrival_count
            + 2 * lane_count
            + (dag.reader_height(depth) - 10 if options.streaming else 0),
            columns[residual],
        )
    for edge, dest in extras:
        join[edge] = (
            base + (4 if options.packed else 8 + 2 * arrival_count) + 2 * lanes[edge],
            entry[dest][1],
        )
    # The last leaf ends 15 units below its fork; the next entry starts
    # 16 below, retaining a full 20px gap for the 15px extraction probe.
    # Streaming has no inline leaves: the next arrival is eight units
    # below the prior fork, and its reader starts at least fourteen below.
    return forks[depth, level[-1]][0] + (4 if options.streaming else 12)


def _layout_dag(
    dag: _Dag,
    options: _CanvasOptions,
    seen: set[State],
    first: dict[State, Edge],
    incoming: list[list[tuple[Edge, State]]],
) -> _Layout:
    members = [
        [residual for residual in level if (depth, residual) in seen]
        for depth, level in enumerate(
            dag.levels if options.streaming else dag.levels[:-1]
        )
    ]
    layout = _Layout(_stem_gaps(dag, options, members), {}, {}, {})
    base = 0
    for depth, level in enumerate(members):
        base = _place_level(
            dag, options, layout, incoming[depth], first, depth, level, base
        )
    return layout


def _loader_reads(dag: _Dag) -> str:
    return loader_reads(dag.original_n, dag.kept)


def _loader_strokes(
    dag: _Dag, fork_row: int
) -> tuple[tuple[int, int], list[list[tuple[int, int]]]]:
    """Return the start point and strokes of the non-streaming input loader."""
    # Loader ink reaches x=-11; the left opcode envelope stops at x=-10.
    start = -12 * dag.original_n - 10, -12
    loader = _StemCursor(*start, (1, 0))
    for op in _loader_reads(dag):
        loader.emit_op(op)
    loader.advance((1, 0), 6)
    loader.advance((0, 1), -loader.x)
    loader.advance((1, 0), fork_row - loader.y)
    loader.finish()
    return start, loader.strokes


@dataclass(slots=True)
class _Router:
    """Builds the node graph while recording the stroke for every stem."""

    dag: _Dag
    options: _CanvasOptions
    layout: _Layout
    strokes: list[list[tuple[int, int]]]
    graph: dict[State, Node]

    def build(self, state: State) -> Node:
        if state in self.graph:
            return self.graph[state]
        depth, residual = state
        dag, options = self.dag, self.options
        if options.streaming and depth == dag.n:
            return self._terminal(state)
        y, x = self.layout.forks[state]
        is_fork = dag.is_fork(residual)
        node = Node("?" if is_fork else "<")
        if options.streaming:
            reader = chain(*dag.reads_at(depth))
            chain_onto(reader, node)
            self.graph[state] = reader
            self._stem(y - dag.reader_height(depth), x, dag.reads_at(depth))
        elif options.destination_moves and depth:
            self.graph[state] = Node("<", next=node)
            self._stem(y - 9, x, "<")
        else:
            self.graph[state] = node
        for bit in (0, 1) if is_fork else (0,):
            self._arm(state, node, bit)
        return self.graph[state]

    def _terminal(self, state: State) -> Node:
        depth, residual = state
        y, x = self.layout.forks[state]
        value = self.dag.constants[residual]
        if value is None:
            raise ValueError("streaming terminal residual is not constant")
        # Cell one starts zero; n >= 2 keeps the fresh output cell
        # within the original tape.
        ops = self.dag.reads_at(depth) + ">" + "+" * value + "o"
        self.graph[state] = chain(*ops)
        self._stem(y - 10, x, ops)
        return self.graph[state]

    def _stem(self, top: int, x: int, ops: str) -> None:
        """Draw ``ops`` down a stem from row ``top``, ending four cells lower."""
        cursor = _StemCursor(top, x, (1, 0))
        for op in ops:
            cursor.emit_op(op)
        cursor.advance((1, 0), 4)
        cursor.finish()
        self.strokes.extend(cursor.strokes)

    def _arm(self, state: State, node: Node, bit: int) -> None:
        dag, options, layout = self.dag, self.options, self.layout
        residual = state[1]
        is_fork = dag.is_fork(residual)
        y, x = layout.forks[state]
        direction = (0, -1) if bit == 0 else (0, 1)
        cursor = _StemCursor(y, x, direction if is_fork else (1, 0))
        if is_fork:
            cursor.advance(direction, layout.gaps[state])
        else:
            cursor.advance((1, 0), 4)
            cursor.advance((0, -1), layout.gaps[state])
        cursor.advance((1, 0), 4)
        value = dag.constants[dag.children[residual][bit]]
        if value is not None and not options.streaming:
            fix = correction(value, bit)
            arm = chain(*fix, "o")
            for op in fix + "o":
                cursor.emit_op(op)
        else:
            arm = self._route_to_child(state, bit, cursor)
        cursor.finish()
        self.strokes.extend(cursor.strokes)
        if is_fork:
            if bit == 0:
                node.zero = arm
            else:
                node.nonzero = arm
        elif options.destination_moves:
            node.op = ""
            node.next = arm
        else:
            node.next = arm.next

    def _route_to_child(self, state: State, bit: int, cursor: _StemCursor) -> Node:
        """Draw the stem from an arm down to its child; return the arm's node."""
        dag, options, layout = self.dag, self.options, self.layout
        depth, residual = state
        if not options.destination_moves:
            cursor.emit_op("<")
        edge = depth, residual, bit
        dest = depth + 1, dag.children[residual][bit]
        tail = self.build(dest)
        if edge in layout.join:
            tail = Node("", goto=tail)
        arm = tail if options.destination_moves else Node("<", next=tail)
        ey, ex = layout.join.get(edge, layout.entry[dest])
        cursor.advance((1, 0), ey - cursor.y)
        dx = ex - cursor.x
        sign = 1 if dx > 0 else -1
        if edge not in layout.join:
            cursor.advance((0, sign), abs(dx))
            cursor.advance(
                (1, 0),
                layout.forks[dest][0]
                - (
                    dag.reader_height(dest[0])
                    if options.streaming
                    else 9
                    if options.destination_moves
                    else 0
                )
                - cursor.y,
            )
        else:
            cursor.advance((0, sign), abs(dx) - 1)
            cursor.advance((1, sign), 1)
        return arm


def _forward_canvas(
    table: str,
    old_area: int,
    options: _CanvasOptions,
    *,
    unit: int = _UNIT,
) -> tuple[Node, CanvasPlan] | None:
    dag = _load_dag(table, options)
    if dag is None:
        return None
    root = (0, dag.levels[0][0])
    seen: set[State] = set()
    first: dict[State, Edge] = {}
    incoming: list[list[tuple[Edge, State]]] = [
        [] for _ in range(dag.n + int(options.streaming))
    ]
    _visit(dag, options, root, seen, first, incoming)
    joins = sum(len(edges) for edges in incoming) - len(first)
    if not joins:
        return None
    # First-fit interval comparisons are quadratic within a layer; reject
    # before routing unless aggregate work is linear in the table.
    if options.packed and sum(len(edges) ** 2 for edges in incoming) > 32 * len(table):
        return None
    layout = _layout_dag(dag, options, seen, first, incoming)
    strokes: list[list[tuple[int, int]]]
    if options.streaming:
        start = layout.forks[root][0] - dag.reader_height(0), layout.forks[root][1]
        strokes = []
    else:
        start, strokes = _loader_strokes(dag, layout.forks[root][0])
    decision = _Router(dag, options, layout, strokes, {}).build(root)
    if options.streaming:
        head = decision
    else:
        head = chain(*_loader_reads(dag))
        chain_onto(head, decision)
    # Streaming uses original_n reads, at most n tests and n joins, three output
    # operations and a halt: original_n+2n+4 <= 5original_n for n >= 2.
    # Constant residuals drain inputs; only original cells zero and one are used.
    # Descending tests remove the loader rewind. At most n-1 join ticks
    # replace those moves: 2n-1 loads, n tests, n-1 moves, n-1 joins, two
    # output ops and one halt tick give 5n. Projection adds fewer than
    # 5(original_n-n) commands and never enlarges the original tape.
    # Moving an arm's '<' onto its destination changes no path's command count.
    plan = stroke_plan(strokes, start, (1, 0), old_area, unit)
    if plan is None:
        return None
    return head, plan
