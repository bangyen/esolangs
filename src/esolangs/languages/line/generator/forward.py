"""Layered residual stems with first-arrival ownership and interior joins."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from esolangs.generation.helpers import (
    _residual_ids,
    _validate_truth_table,
    essential_inputs,
    read_at,
)

from .render import (
    _UNIT,
    Node,
    _Cursor,
    chain,
    chain_onto,
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


def streaming_canvas(
    table: str, old_area: int, *, unit: int = _UNIT
) -> tuple[Node, CanvasPlan] | None:
    """Read in input order on shared stems, overwriting cell zero."""
    return _fold_canvas(table, old_area, projected=False, unit=unit)


def projected_streaming_canvas(
    table: str, old_area: int, *, unit: int = _UNIT
) -> tuple[Node, CanvasPlan] | None:
    """Share essential residuals while draining ignored reads on their stems."""
    return _fold_canvas(table, old_area, projected=True, unit=unit)


def _fold_canvas(
    table: str, old_area: int, *, projected: bool, unit: int
) -> tuple[Node, CanvasPlan] | None:
    """Return a complete fold within 5n commands that beats ``old_area``, else None."""
    dag = _load_dag(table, projected=projected)
    if dag is None:
        return None
    root = (0, dag.levels[0][0])
    seen: set[State] = set()
    first: dict[State, Edge] = {}
    incoming: list[list[tuple[Edge, State]]] = [[] for _ in range(dag.n + 1)]
    _visit(dag, root, seen, first, incoming)
    if sum(len(edges) for edges in incoming) == len(first):  # no shared join
        return None
    layout = _layout_dag(dag, seen, first, incoming)
    start = layout.forks[root][0] - dag.reader_height(0), layout.forks[root][1]
    router = _Router(dag, layout, [], {})
    head = router.build(root)
    # original_n reads, at most n tests and n joins, three output operations
    # and a halt: original_n+2n+4 <= 5original_n for n >= 2.  Constant
    # residuals drain inputs; only original cells zero and one are used.
    # Projection adds fewer than 5(original_n-n) commands and never enlarges
    # the original tape.  Moving an arm's '<' onto its destination changes
    # no path's command count.
    plan = stroke_plan(router.strokes, start, (1, 0), old_area, unit)
    return None if plan is None else (head, plan)


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


def _load_dag(table: str, *, projected: bool) -> _Dag | None:
    """Return the residual DAG over all inputs (essential ones if ``projected``)."""
    original_n = _validate_truth_table(table)
    kept = essential_inputs(table, original_n) if projected else list(range(original_n))
    if projected and len(kept) == original_n:
        return None
    if len(kept) < 2:
        return None
    reduced = read_at(table, kept, original_n) if projected else table
    levels, children, constants = _residual_ids(reduced, len(kept))
    return _Dag(original_n, kept, children, constants, levels)


def _visit(
    dag: _Dag,
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
        edge = depth, residual, bit
        dest = depth + 1, target
        first.setdefault(dest, edge)
        incoming[depth + 1].append((edge, dest))
        _visit(dag, dest, seen, first, incoming)


def _stem_gaps(members: list[list[int]]) -> dict[State, int]:
    # Columns are multiples of eight; outgoing rails are 2 or 6 mod 8.  This
    # separates rails from nodes and the +/-1 opcode ink.
    return {
        (depth, residual): 2
        for depth, level in enumerate(members)
        for residual in level
    }


def _rail(layout: _Layout, edge: Edge) -> int:
    """Column of the rail leaving an edge's source fork."""
    gap = layout.gaps[edge[:2]]
    return layout.forks[edge[0], edge[1]][1] + (-gap if edge[2] == 0 else gap)


def _level_columns(
    gaps: dict[State, int], depth: int, level: list[int]
) -> dict[int, int]:
    columns = {}
    column = 0
    previous_gap = gaps[depth, level[0]]
    for index, residual in enumerate(level):
        gap = gaps[depth, residual]
        if index:
            column += previous_gap + gap + 4
        columns[residual] = column
        previous_gap = gap
    return columns


def _level_lanes(
    layout: _Layout,
    first: dict[State, Edge],
    depth: int,
    level: list[int],
    extras: list[tuple[Edge, State]],
    columns: dict[int, int],
) -> tuple[dict[Edge, int], int, dict[Edge, int], int]:
    """One layer's ``(arrival_lanes, arrival_count, join_lanes, join_lane_count)``."""
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
    lanes, lane_count = _join_lanes(join_spans)
    return arrival_lanes, arrival_count, lanes, lane_count


def _place_level(
    dag: _Dag,
    layout: _Layout,
    incoming: list[tuple[Edge, State]],
    first: dict[State, Edge],
    depth: int,
    level: list[int],
    base: int,
) -> int:
    """Place one layer's forks, entries and joins; return the next base row."""
    forks, entry, join = layout.forks, layout.entry, layout.join
    extras = [(edge, dest) for edge, dest in incoming if first[dest] != edge]
    columns = _level_columns(layout.gaps, depth, level)
    arrival_lanes, arrival_count, lanes, lane_count = _level_lanes(
        layout, first, depth, level, extras, columns
    )
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
            + 20
            + 2 * arrival_count
            + 2 * lane_count
            + dag.reader_height(depth)
            - 10,
            columns[residual],
        )
    for edge, dest in extras:
        join[edge] = (
            base + 8 + 2 * arrival_count + 2 * lanes[edge],
            entry[dest][1],
        )
    # The last leaf ends 15 units below its fork; the next entry starts
    # 16 below, retaining a full 20px gap for the 15px extraction probe.
    # Streaming has no inline leaves: the next arrival is eight units
    # below the prior fork, and its reader starts at least fourteen below.
    return forks[depth, level[-1]][0] + 4


def _layout_dag(
    dag: _Dag,
    seen: set[State],
    first: dict[State, Edge],
    incoming: list[list[tuple[Edge, State]]],
) -> _Layout:
    members = [
        [residual for residual in level if (depth, residual) in seen]
        for depth, level in enumerate(dag.levels)
    ]
    layout = _Layout(_stem_gaps(members), {}, {}, {})
    base = 0
    for depth, level in enumerate(members):
        base = _place_level(dag, layout, incoming[depth], first, depth, level, base)
    return layout


@dataclass(slots=True)
class _Router:
    """Builds the node graph while recording the stroke for every stem."""

    dag: _Dag
    layout: _Layout
    strokes: list[list[tuple[int, int]]]
    graph: dict[State, Node]

    def build(self, state: State) -> Node:
        if state in self.graph:
            return self.graph[state]
        depth, residual = state
        dag = self.dag
        if depth == dag.n:
            return self._terminal(state)
        y, x = self.layout.forks[state]
        is_fork = dag.is_fork(residual)
        node = Node("?" if is_fork else "<")
        reader = chain(*dag.reads_at(depth))
        chain_onto(reader, node)
        self.graph[state] = reader
        self._stem(y - dag.reader_height(depth), x, dag.reads_at(depth))
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
        dag, layout = self.dag, self.layout
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
        arm = self._route_to_child(state, bit, cursor)
        cursor.finish()
        self.strokes.extend(cursor.strokes)
        if is_fork:
            if bit == 0:
                node.zero = arm
            else:
                node.nonzero = arm
        else:
            node.op = ""
            node.next = arm

    def _route_to_child(self, state: State, bit: int, cursor: _StemCursor) -> Node:
        """Draw the stem from an arm down to its child; return the arm's node."""
        dag, layout = self.dag, self.layout
        depth, residual = state
        edge = depth, residual, bit
        dest = depth + 1, dag.children[residual][bit]
        tail = self.build(dest)
        if edge in layout.join:
            tail = Node("", goto=tail)
        ey, ex = layout.join.get(edge, layout.entry[dest])
        cursor.advance((1, 0), ey - cursor.y)
        dx = ex - cursor.x
        sign = 1 if dx > 0 else -1
        if edge not in layout.join:
            cursor.advance((0, sign), abs(dx))
            cursor.advance(
                (1, 0),
                layout.forks[dest][0] - dag.reader_height(dest[0]) - cursor.y,
            )
        else:
            cursor.advance((0, sign), abs(dx) - 1)
            cursor.advance((1, sign), 1)
        return tail
