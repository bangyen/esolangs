"""Layered residual stems with first-arrival ownership and interior joins."""

from __future__ import annotations

from collections import deque

from esolangs.tools.helpers import (
    _residual_ids,
    _validate_truth_table,
    essential_inputs,
    permute_truth_table,
    read_at,
)

from .render import _UNIT, Canvas, Node, _arrowhead, _Cursor, chain
from .shared import CanvasPlan

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


def forward_canvas(
    table: str, old_area: int, *, unit: int = _UNIT
) -> tuple[Node, CanvasPlan] | None:
    """Return a smaller descending residual DAG with at most 5n commands."""
    return _forward_canvas(table, old_area, unit=unit, destination_moves=False)


def destination_canvas(
    table: str, old_area: int, *, unit: int = _UNIT
) -> tuple[Node, CanvasPlan] | None:
    """Share pointer moves on destination stems with separated narrow forks."""
    return _forward_canvas(table, old_area, unit=unit, destination_moves=True)


def streaming_canvas(
    table: str, old_area: int, *, unit: int = _UNIT
) -> tuple[Node, CanvasPlan] | None:
    """Read in input order on shared stems, overwriting cell zero."""
    return _forward_canvas(
        table, old_area, unit=unit, destination_moves=True, streaming=True
    )


def centered_streaming_canvas(
    table: str, old_area: int, *, unit: int = _UNIT
) -> tuple[Node, CanvasPlan] | None:
    """Center streamed layers on eight-unit columns to shorten arrivals."""
    return _forward_canvas(
        table,
        old_area,
        unit=unit,
        destination_moves=True,
        streaming=True,
        centered=True,
    )


def median_streaming_canvas(
    table: str, old_area: int, *, unit: int = _UNIT
) -> tuple[Node, CanvasPlan] | None:
    """Order centered streamed layers by the lower median incoming rail."""
    return _forward_canvas(
        table,
        old_area,
        unit=unit,
        destination_moves=True,
        streaming=True,
        centered=True,
        median_order=True,
    )


def packed_streaming_canvas(
    table: str, old_area: int, *, unit: int = _UNIT
) -> tuple[Node, CanvasPlan] | None:
    """Pack median-ordered arrivals and joins with per-stem precedence."""
    return _forward_canvas(
        table,
        old_area,
        unit=unit,
        destination_moves=True,
        streaming=True,
        centered=True,
        median_order=True,
        packed=True,
    )


def _forward_canvas(
    table: str,
    old_area: int,
    *,
    destination_moves: bool,
    unit: int = _UNIT,
    streaming: bool = False,
    centered: bool = False,
    median_order: bool = False,
    packed: bool = False,
) -> tuple[Node, CanvasPlan] | None:
    original_n = _validate_truth_table(table)
    kept = list(range(original_n)) if streaming else essential_inputs(table, original_n)
    n = len(kept)
    if n < 2:
        return None
    reduced = table if streaming else read_at(table, kept, original_n)
    levels, children, constants = _residual_ids(
        reduced
        if streaming
        else permute_truth_table(reduced, tuple(range(n - 1, -1, -1))),
        n,
    )
    root = (0, levels[0][0])
    seen: set[State] = set()
    first: dict[State, Edge] = {}
    incoming: list[list[tuple[Edge, State]]] = [[] for _ in range(n + int(streaming))]

    def visit(state: State) -> None:
        if state in seen:
            return
        seen.add(state)
        depth, residual = state
        if depth == n:
            return
        arms = (0, 1) if children[residual][0] != children[residual][1] else (0,)
        for bit in arms:
            target = children[residual][bit]
            if streaming or constants[target] is None:
                edge = depth, residual, bit
                dest = depth + 1, target
                first.setdefault(dest, edge)
                incoming[depth + 1].append((edge, dest))
                visit(dest)

    visit(root)
    joins = sum(len(edges) for edges in incoming) - len(first)
    if not joins:
        return None
    # First-fit interval comparisons are quadratic within a layer; reject
    # before routing unless aggregate work is linear in the table.
    if packed and sum(len(edges) ** 2 for edges in incoming) > 32 * len(table):
        return None
    members = [
        [residual for residual in level if (depth, residual) in seen]
        for depth, level in enumerate(levels if streaming else levels[:-1])
    ]
    gaps = {
        (depth, residual): (
            2
            if streaming
            or all(constants[children[residual][bit]] is None for bit in (0, 1))
            else 10
        )
        if destination_moves
        else 8
        for depth, level in enumerate(members)
        for residual in level
    }
    # Destination-mode columns are multiples of eight; outgoing rails are
    # 2 or 6 mod 8. This separates rails from nodes and the +/-1 opcode ink.
    # Gaps 2/8 with variable pitch failed native dense n=8 extraction;
    # 2/10 preserves the residue separation and executes every row.
    forks: dict[State, tuple[int, int]] = {}
    entry: dict[State, tuple[int, int]] = {}
    join: dict[Edge, tuple[int, int]] = {}
    base = 0
    for depth, level in enumerate(members):
        if median_order and depth:
            parents: dict[int, list[int]] = {residual: [] for residual in level}
            for edge, dest in incoming[depth]:
                parents[dest[1]].append(
                    forks[edge[0], edge[1]][1]
                    + (-gaps[edge[:2]] if edge[2] == 0 else gaps[edge[:2]])
                )

            ranked = []
            for residual, rails in parents.items():
                rails.sort()
                ranked.append((rails[(len(rails) - 1) // 2], residual))

            # One forward pass preserves eight-unit rail separation. Native
            # dense8 falls from 37,795,200 to 36,982,400 scale-one pixels.
            level = [residual for median, residual in sorted(ranked)]
        extras = [(edge, dest) for edge, dest in incoming[depth] if first[dest] != edge]
        columns = {}
        column = 0
        previous_gap = gaps[depth, level[0]]
        for index, residual in enumerate(level):
            gap = gaps[depth, residual]
            if index:
                column += previous_gap + gap + 4 if destination_moves else 20
            columns[residual] = column
            previous_gap = gap
        if centered:
            # Eight-unit translation preserves node/rail residue separation.
            offset = -8 * (column // 16)
            columns = {residual: x + offset for residual, x in columns.items()}
        join_spans = [
            (
                edge,
                forks[edge[0], edge[1]][1]
                + (-gaps[edge[:2]] if edge[2] == 0 else gaps[edge[:2]]),
                columns[dest[1]],
            )
            for edge, dest in extras
        ]
        lanes, lane_count = _join_lanes(join_spans)
        arrivals = (
            [
                (
                    first[depth, residual],
                    forks[first[depth, residual][0], first[depth, residual][1]][1]
                    + (
                        -gaps[first[depth, residual][:2]]
                        if first[depth, residual][2] == 0
                        else gaps[first[depth, residual][:2]]
                    ),
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
        if packed:
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
        # Disjoint arrival/join spans reuse rows. At n=22 majority, scale 1,
        # this emits 87,270,400 pixels versus 123,110,400 (29.1%); both native
        # programs pass 37 rows with the same 98-command maximum.
        # In the original mode, all 81 adjacent arm-shape pairs at pitch 20 keep
        # opcode ink at least one unit apart (20px > the 15px star probe).
        # Entry/join lanes contain no opcodes and use two-unit spacing.
        for residual in level:
            state = depth, residual
            entry[state] = (
                base + 4 + 2 * (arrival_lanes[first[state]] if depth else 0),
                columns[residual],
            )
            forks[state] = (
                base
                + (20 if destination_moves else 16)
                + 2 * arrival_count
                + 2 * lane_count,
                columns[residual],
            )
        for edge, dest in extras:
            join[edge] = (
                base + (4 if packed else 8 + 2 * arrival_count) + 2 * lanes[edge],
                entry[dest][1],
            )
        # The last leaf ends 15 units below its fork; the next entry starts
        # 16 below, retaining a full 20px gap for the 15px extraction probe.
        # Streaming has no inline leaves: the next arrival is eight units
        # below the prior fork, and its reader starts at least fourteen below.
        base = forks[depth, level[-1]][0] + (4 if streaming else 12)

    if streaming:
        start = forks[root][0] - 10, forks[root][1]
        strokes = []
    else:
        reads = "".join(
            "i" + (">" if index in kept and index < original_n - 1 else "")
            for index in range(original_n)
        )
        if kept[-1] < original_n - 1:
            reads += "<"
        # Loader ink reaches x=-11; the left opcode envelope stops at x=-10.
        start = -12 * original_n - 10, -12
        loader = _StemCursor(*start, (1, 0))
        for op in reads:
            loader.emit_op(op)
        loader.advance((1, 0), 6)
        loader.advance((0, 1), -loader.x)
        loader.advance((1, 0), forks[root][0] - loader.y)
        loader.finish()
        strokes = loader.strokes[:]
    graph: dict[State, Node] = {}

    def build(state: State) -> Node:
        if state in graph:
            return graph[state]
        depth, residual = state
        y, x = forks[state]
        if streaming and depth == n:
            value = constants[residual]
            if value is None:
                raise ValueError("streaming terminal residual is not constant")
            # Cell one starts zero; n >= 2 keeps the fresh output cell
            # within the original tape.
            ops = ">" + "+" * value + "o"
            graph[state] = chain(*ops)
            cursor = _StemCursor(y - 10, x, (1, 0))
            for op in ops:
                cursor.emit_op(op)
            cursor.advance((1, 0), 4)
            cursor.finish()
            strokes.extend(cursor.strokes)
            return graph[state]
        is_fork = children[residual][0] != children[residual][1]
        node = Node("?" if is_fork else "<")
        if streaming:
            graph[state] = Node("i", next=node)
        else:
            graph[state] = Node("<", next=node) if destination_moves and depth else node
        if streaming or (destination_moves and depth):
            pre = _StemCursor(y - (10 if streaming else 9), x, (1, 0))
            pre.emit_op("i" if streaming else "<")
            pre.advance((1, 0), 4)
            pre.finish()
            strokes.extend(pre.strokes)
        for bit in (0, 1) if is_fork else (0,):
            direction = (0, -1) if bit == 0 else (0, 1)
            cursor = _StemCursor(y, x, direction if is_fork else (1, 0))
            if is_fork:
                cursor.advance(direction, gaps[state])
            else:
                cursor.advance((1, 0), 4)
                cursor.advance((0, -1), gaps[state])
            cursor.advance((1, 0), 4)
            target = children[residual][bit]
            value = constants[target]
            if value is not None and not streaming:
                correction = "" if value == bit else "+" if value else "-"
                arm = chain(*correction, "o")
                for op in correction + "o":
                    cursor.emit_op(op)
            else:
                if not destination_moves:
                    cursor.emit_op("<")
                edge = depth, residual, bit
                dest = depth + 1, target
                tail = build(dest)
                if edge in join:
                    tail = Node("", goto=tail)
                arm = tail if destination_moves else Node("<", next=tail)
                ey, ex = join.get(edge, entry[dest])
                cursor.advance((1, 0), ey - cursor.y)
                dx = ex - cursor.x
                sign = 1 if dx > 0 else -1
                if edge not in join:
                    cursor.advance((0, sign), abs(dx))
                    cursor.advance(
                        (1, 0),
                        forks[dest][0]
                        - (10 if streaming else 9 if destination_moves else 0)
                        - cursor.y,
                    )
                else:
                    cursor.advance((0, sign), abs(dx) - 1)
                    cursor.advance((1, sign), 1)
            cursor.finish()
            strokes.extend(cursor.strokes)
            if is_fork:
                if bit == 0:
                    node.zero = arm
                else:
                    node.nonzero = arm
            else:
                if destination_moves:
                    node.op = ""
                    node.next = arm
                else:
                    node.next = arm.next
        return graph[state]

    decision = build(root)
    if streaming:
        head = decision
    else:
        head = chain(*reads)
        tail = head
        while tail.next is not None:
            tail = tail.next
        tail.next = decision
    points = [point for stroke in strokes for point in stroke]
    top, bottom = min(y for y, _ in points), max(y for y, _ in points)
    left, right = min(x for _, x in points), max(x for _, x in points)
    width, height = (right - left + 2) * unit, (bottom - top + 2) * unit
    if width * height >= old_area:
        return None

    def rasterize() -> Canvas:
        canvas = Canvas(width, height)
        for stroke in strokes:
            canvas.line(
                [((x - left + 1) * unit, (y - top + 1) * unit) for y, x in stroke]
            )
        _arrowhead(
            canvas,
            (start[0] - top + 1) * unit,
            (start[1] - left + 1) * unit,
            (1, 0),
            unit=unit,
        )
        return canvas

    # Streaming uses n reads, at most n tests and n joins, three output
    # operations and a halt: 3n+4 <= 5n for n >= 2. Constant residuals
    # drain the remaining inputs. Only original cells zero and one are used.
    # Descending tests remove the loader rewind. At most n-1 join ticks
    # replace those moves: 2n-1 loads, n tests, n-1 moves, n-1 joins, two
    # output ops and one halt tick give 5n. Projection adds fewer than
    # 5(original_n-n) commands and never enlarges the original tape.
    # Moving an arm's '<' onto its destination changes no path's command count.
    return head, CanvasPlan(rasterize, width * height)
