"""Render Line programs to PNG images.

Line (https://esolangs.org/wiki/Line) has no text format at all -- the wiki
page defines every instruction as a hand-drawn curve shape (image files), and
is tagged "Unimplemented".  This module is a standalone renderer, not an
interpreter: it takes a small opcode sequence, lays it out as a path on a
grid, and rasterizes it into an image shaped like the wiki's own examples --
straight runs, unlabeled corners, a small diagonal kink for each of the seven
instructions, and a filled triangular arrowhead marking the cursor.

The kink shapes below (``_OPS``) were measured pixel-by-pixel directly from
the wiki's own reference images (``Lineanim4.png`` through ``Lineanim11.png``,
plus ``Lineanim6.png`` for repeats), and fall into two distinct families, not
one shared template -- see the comment directly above ``_OPS`` for the full
measurement.  In short: ``+``/``-`` are a single diagonal jog with no
sideways connector, and repeating one back to back *stretches that same
diagonal* rather than drawing separate kinks (``+++`` measured at exactly 3x
a lone ``+``'s diagonal length in ``Lineanim6.png``).  ``>``/``<``/``i``/``o``
each have a short *purely sideways* connector (not another diagonal) bridging
one or two diagonal legs, are not mergeable the same way, and are always
drawn as their own fixed-size kink even when repeated.  This module does not
invent new geometry -- it replays those measured run-length templates at an
arbitrary grid position and heading.

Conditional turn (``?``) is not a 2-endpoint kink like the others: the wiki's
``Lineanim9.png`` shows a real T-branch, one incoming stem meeting a
horizontal bar with an exit to either side.  ``_layout`` gives it two
children (taken on nonzero vs zero) instead of one successor.

This is the generation direction only, and is intentionally simpler than
extracting a program back out of an image: a generator controls its own
layout, so it can keep unrelated strokes far enough apart that they never
touch except at an intended branch -- sidestepping the crossing-vs-merge
ambiguity that makes the reverse (image -> program) direction hard.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

try:
    from PIL import Image, ImageDraw
except ImportError as _exc:  # pragma: no cover - environment guard
    raise ImportError(
        "Rendering Line programs requires Pillow: pip install Pillow"
    ) from _exc

# One grid unit in output pixels.  The wiki's own images use roughly this
# scale for a single straight run between kinks.
_UNIT = 20

# Cardinal headings as (dy, dx) unit vectors in grid space.  Diagonal jogs
# combine a heading with the perpendicular ("right"/"left") direction, so
# they move one step forward *and* one step sideways at once -- matching the
# true 45-degree kink measured from the wiki's images (e.g. the `+` opcode's
# middle run was `(-1, 1)` per step: forward and right together), not two
# separate orthogonal legs.
_FORWARD = (1, 0)


def _turn_right(d: tuple[int, int]) -> tuple[int, int]:
    dy, dx = d
    return dx, -dy


def _turn_left(d: tuple[int, int]) -> tuple[int, int]:
    dy, dx = d
    return -dx, dy


def _diag_right(d: tuple[int, int]) -> tuple[int, int]:
    """Forward-and-right diagonal: one step in ``d``, one step turned right."""
    dy, dx = d
    ry, rx = _turn_right(d)
    return dy + ry, dx + rx


def _diag_left(d: tuple[int, int]) -> tuple[int, int]:
    """Forward-and-left diagonal: one step in ``d``, one step turned left."""
    dy, dx = d
    ly, lx = _turn_left(d)
    return dy + ly, dx + lx


def _horiz_right(d: tuple[int, int]) -> tuple[int, int]:
    """Pure sideways step, turned right relative to ``d`` (no forward motion).

    Distinguishes ``>``/``<``/``i``/``o`` from ``+``/``-``: measured directly
    from the wiki's own reference images (Lineanim7/8/10/11.png), each of
    those four kinks includes a short *purely sideways* connector -- not
    another 45-degree diagonal -- bridging its diagonal leg(s), which
    ``+``/``-`` do not have at all.
    """
    return _turn_right(d)


def _horiz_left(d: tuple[int, int]) -> tuple[int, int]:
    """Pure sideways step, turned left relative to ``d`` (no forward motion)."""
    return _turn_left(d)


def _rotate(d: tuple[int, int], heading: tuple[int, int]) -> tuple[int, int]:
    """Rotate a direction defined relative to "forward" onto ``heading``."""
    dy, dx = d
    hy, hx = heading
    # Forward (1, 0) maps to heading; right/left rotate along with it.
    ly, lx = _turn_left(heading)
    return hy * dy + ly * dx, hx * dy + lx * dx


# Each opcode is a sequence of (relative_direction, run_length) segments,
# relative to the cursor's current heading, replaying the run-length
# breakdown measured pixel-by-pixel from the wiki's own reference images at
# _UNIT-sized steps.  Two distinct kink families, confirmed by measuring
# every one of Lineanim4/5/6/7/8/10/11.png rather than assuming a shared
# template:
#
# * `+`/`-` (Lineanim4.png, Lineanim5.png) are a single diagonal jog with no
#   sideways connector -- `vertical(2) -> diagonal(1) -> vertical(2)`.  Their
#   diagonal leg's *length in units is the run's opcode count*, not a fixed
#   1: Lineanim6.png shows three consecutive `+` as one continuous diagonal
#   3 units long, not three separate kinks stitched together (confirmed by
#   measuring its diagonal run at exactly 3x a single `+`'s).  `_OPS["+"]`
#   and `_OPS["-"]` below are therefore templates over a `count` parameter,
#   built by :func:`_op_segments` rather than being a fixed list like the
#   others -- see :func:`_Cursor.emit_op`, which is what actually supplies
#   `count` from consecutive same-op runs in the node chain.
# * `>`/`<`/`i`/`o` (Lineanim7/8/10/11.png) additionally have a short *pure
#   sideways* connector (no forward motion at all -- see `_horiz_right`/
#   `_horiz_left`) bridging their diagonal leg(s), which is what visually
#   distinguishes them from the plain `+`/`-` kink; `i`/`o` have one more
#   diagonal leg than `>`/`<` (confirmed: Lineanim10.png's path is taller
#   than Lineanim7.png's by almost exactly one extra unit-diagonal's worth of
#   rows).  Unlike `+`/`-`, repeats of these are never merged -- there is no
#   wiki example showing it, and each is always drawn as its own fixed-size
#   kink even back-to-back with an identical one.
_OPS: dict[str, list[tuple[tuple[int, int], int]]] = {
    ">": [
        (_FORWARD, 2),
        (_diag_right(_FORWARD), 1),
        (_horiz_left(_FORWARD), 1),
        (_FORWARD, 2),
    ],
    "<": [
        (_FORWARD, 2),
        (_diag_left(_FORWARD), 1),
        (_horiz_right(_FORWARD), 1),
        (_FORWARD, 2),
    ],
    "i": [
        (_FORWARD, 2),
        (_diag_right(_FORWARD), 1),
        (_horiz_left(_FORWARD), 2),
        (_diag_right(_FORWARD), 1),
        (_FORWARD, 2),
    ],
    "o": [
        (_FORWARD, 2),
        (_horiz_left(_FORWARD), 1),
        (_diag_right(_FORWARD), 2),
        (_horiz_left(_FORWARD), 1),
        (_FORWARD, 2),
    ],
}


def _op_segments(op: str, count: int) -> list[tuple[tuple[int, int], int]]:
    """Look up one opcode's kink template, expanding `+`/`-`'s run by `count`.

    `+`/`-` are the only opcodes whose repeats visually merge (see the
    `_OPS` comment above) -- their diagonal leg is `count` units long rather
    than the fixed length every other entry in `_OPS` uses.
    """
    if op == "+":
        return [(_FORWARD, 2), (_diag_right(_FORWARD), count), (_FORWARD, 2)]
    if op == "-":
        return [(_FORWARD, 2), (_diag_left(_FORWARD), count), (_FORWARD, 2)]
    return _OPS[op]


@dataclass
class _Cursor:
    y: int
    x: int
    heading: tuple[int, int]
    strokes: list[list[tuple[int, int]]] = field(default_factory=list)
    _current: list[tuple[int, int]] = field(default_factory=list)
    # Every pixel any stroke has drawn so far, across the *whole* program
    # being laid out -- shared by reference among a cursor and every child
    # cursor `branch()` creates from it, so a later loop-back detour
    # (`_close_loop`) can route around ink from sibling arms and the trunk,
    # not just its own cursor's strokes.  `None` (the default) means
    # occupancy tracking is off, matching every existing caller/test that
    # never routes a loop-back and so never needs it.
    occupied: set[tuple[int, int]] | None = None

    def __post_init__(self) -> None:
        self._current = [(self.y, self.x)]

    def advance(self, direction: tuple[int, int], steps: int = 1) -> None:
        for _ in range(steps):
            self.y += direction[0]
            self.x += direction[1]
            self._current.append((self.y, self.x))
        self.heading = direction

    def emit_op(self, op: str, count: int = 1) -> None:
        """Emit one opcode's kink, all legs rotated onto the heading at entry.

        The heading used to rotate each leg is frozen at the start of the
        opcode: the diagonal jog's own direction is not a cardinal heading,
        so letting it become ``self.heading`` mid-opcode would make the
        following leg drift instead of returning to the original travel
        direction, as the wiki's images show (vertical in, diagonal jog,
        vertical out -- same orientation before and after).

        ``count`` merges that many consecutive identical opcodes into one
        stretched kink -- only meaningful for ``+``/``-`` (see the ``_OPS``
        comment); :func:`_layout` is what actually counts a run of identical
        nodes and passes it through here.
        """
        entry_heading = self.heading
        for rel_dir, run in _op_segments(op, count):
            self.advance(_rotate(rel_dir, entry_heading), run)
        self.heading = entry_heading

    def branch(self) -> tuple[_Cursor, _Cursor]:
        """Split into two cursors (taken / not-taken) at the current point.

        Models the conditional-turn instruction's T-branch (measured from
        ``Lineanim9.png``): one incoming stem, two outgoing arms, turning
        right when the tape cell is zero and left otherwise.
        """
        self.finish()
        right = _Cursor(
            self.y, self.x, _turn_right(self.heading), occupied=self.occupied
        )
        left = _Cursor(self.y, self.x, _turn_left(self.heading), occupied=self.occupied)
        return right, left

    def finish(self) -> None:
        if len(self._current) > 1:
            self.strokes.append(self._current)
            if self.occupied is not None:
                self.occupied.update(self._current)
        self._current = [(self.y, self.x)]


@dataclass
class Node:
    """One step of a Line program: an opcode, or a conditional branch.

    ``op`` is one of ``+ - < > i o`` for a straight-through instruction, or
    ``?`` for the conditional turn.  ``next`` is the following node for a
    straight-through op; ``zero``/``nonzero`` are the two branches taken by
    ``?``, matching the wiki's "turn right if the current cell is 0,
    otherwise turn left" rule.

    ``goto`` marks a real drawn loop-back: after this node's own op (if any)
    runs, instead of continuing to ``next`` (which must be ``None`` when
    ``goto`` is set -- a node either continues straight or jumps back, not
    both), the layout closes a detour back to a point strictly inside the
    stem leading into whatever ``?`` node ``goto`` points at -- not the fork's
    own vertex (see :func:`_layout`'s ``_close_loop`` for why: forcing the
    detour to arrive with the fork's own arrival heading always retraces the
    stem's own line, since two straight approaches from the same heading
    landing on the same point are the same line).  A mid-stem reconnection
    is exactly the shape :mod:`simulate`'s ``find_merge`` already handles as
    its primary real-world case (confirmed on the wiki's own
    ``addition.png`` fixture, whose loop-body arm reconnects strictly inside
    its incoming stem's straight run rather than onto any recorded vertex).
    This is how a compiler (e.g. a brainfuck-to-Line translator) expresses
    ``[...]``: a ``?`` fork whose ``nonzero`` arm is the loop body ending in
    a node whose ``goto`` points back at the fork itself, and whose ``zero``
    arm is the code following the loop.
    """

    op: str
    next: Node | None = None
    zero: Node | None = None
    nonzero: Node | None = None
    goto: Node | None = None


def chain(*ops: str) -> Node:
    """Build a straight-through Node chain from an opcode string, e.g. "+++"."""
    head: Node | None = None
    tail: Node | None = None
    for op in ops:
        node = Node(op)
        if head is None:
            head = node
        else:
            assert tail is not None
            tail.next = node
        tail = node
    if head is None:
        raise ValueError("chain() requires at least one opcode")
    return head


# The only opcodes whose consecutive repeats visually merge into one
# stretched kink rather than drawing separately, back to back (see the
# `_OPS` comment in this module -- confirmed against Lineanim6.png, and
# there is no wiki example showing merged >/</i/o).
_MERGEABLE = {"+", "-"}

# Two earlier approaches to closing a loop-back were tried and rejected:
#
# * A fixed diagonal-then-straight detour onto the fork's own vertex,
#   arriving with the fork's own heading: rejected because forcing the final
#   leg to match that heading means retracing the stem's own line exactly
#   (two straight approaches from the same heading landing on the same point
#   are the same line) -- no clearance fixes that, since the final leg's
#   geometry is fixed by the target point and heading alone.  `_layout` now
#   targets a point strictly *inside* the stem instead (see its own
#   docstring), which removes the heading constraint entirely --
#   :mod:`simulate`'s ``find_merge`` accepts a mid-segment reconnection from
#   any direction.
# * An escalating-clearance heuristic (step out perpendicular by a growing
#   distance, then a direct two-leg run onto the target): worked for a single
#   flat loop, but a nested loop's outer detour has no reliable "sideways"
#   direction that clears the inner loop's own already-drawn rectangle,
#   which can span the entire width the heuristic tries to step past.
#
# `_close_loop` instead does real pathfinding: A* over the pixel grid,
# 4-directional only (never diagonal -- see :func:`_route_legs`'s docstring
# for why), blocked by every pixel in `occupied` except the target itself.
# This is exact (no coarse-cell rounding to reintroduce collisions, unlike an
# even earlier cell-grid-BFS attempt) and finds a route around arbitrarily
# shaped existing ink, including a previously-closed inner loop's own
# rectangle.
# `_route_legs` searches within a padded bounding box around start/target,
# not the unbounded canvas: a real Line drawing's ink is sparse relative to
# its own bounding box (thin 1px-wide strokes), so an unbounded search that
# fails to find a route wastes enormous time re-discovering that most of a
# huge, mostly-empty canvas is reachable before ever giving up -- confirmed
# directly: a plain flood fill (independent of this module's own A*) from a
# real failing case's start pixel did not finish within two minutes.  The
# padding below starts modest and doubles on each retry (see `_close_loop`'s
# caller, which is what actually widens it) rather than search unbounded
# from the first attempt.
_MAX_ROUTE_SEARCH = 300_000  # pragma: no mutate - generous per-attempt search-node cap


# Cost, in path-length cells, added for each cell of a route that lands inside
# an ``avoid`` region (a later detour's departure neighborhood -- see
# :func:`_route_pending`).  Routes here run 100-250 cells and skirting a
# doorstep costs ~10-20 cells of extra travel, so one unit's worth per
# trespassed cell makes a crossing effectively a last resort (a 5-cell
# incursion costs as much as 100 cells of honest travel) while never becoming
# a wall: when a doorstep's neighborhood holds the only lane there is, the
# route pays and crosses on the shortest chord instead of failing outright.
# That "pays and crosses" case is real, not theoretical -- see
# :func:`_route_pending` for the measured depth-4 geometry that has no
# non-crossing alternative.
_AVOID_PENALTY = _UNIT


# How many *grid cells* of empty space a detour leg must keep between itself
# and any unrelated existing ink, beyond simply not overlapping it.  One cell
# here is `_UNIT` raster pixels of real separation, since the router works
# entirely in cursor-grid space and `render` scales to pixels only when
# rasterizing.
#
# Non-overlap alone is not enough for the extractor to read a drawing
# correctly.  Two strokes running through directly *abutting* grid cells
# share no cell at all, but rasterize into a contiguous 2-cell-wide ribbon of
# ink -- and `lattice._band_lit` deliberately probes the exact ray *plus one
# pixel to each side*, to absorb hand-drawn stroke slop (see `lattice.py`'s
# module docstring), so it reads the neighbor as a real lit direction.  An
# extra lit direction at an ordinary point is exactly what turns it into a
# spurious 3-lit `"fork"`, which `simulate` then executes as a conditional
# turn.  A cell of mandated clearance restores the band probe's
# unambiguity: with a gap, its off-center rays fall on background, so only
# the stroke actually being walked lights up.
#
# Note the *nested-loop regression itself* was caused by a route touching
# *itself*, which `_self_approaches` is what actually fixes -- per-stroke
# attribution on `++[>++[>+<-]<-]>>.` showed all three arms of the spurious
# junction belonging to one single 530-cell detour.  This constant addresses
# the separate between-stroke case, and is pinned independently by
# `test_bf_to_line.py`'s `TestStrokeSeparation`: at 0, every program it
# checks develops between-stroke adjacency (up to 76 consecutive abutting
# cells on `++[>++[>+<-]<-]>>+++.`), at 1 none does.
#
# That test exists because the ordinary suites do *not* catch this on their
# own -- they assert on program output, and a drawing can rasterize a 2px
# ribbon while still happening to extract and execute correctly.  Setting
# this to 0 left every other test passing, which is exactly why measuring
# stroke separation directly was needed to pin it.
_CLEARANCE = 1


# Radius, in *grid cells* (not raster pixels -- everything the router works
# in is cursor-grid space, which `render` scales by `_UNIT` only at raster
# time), around a detour's own departure point within which `_CLEARANCE` is
# waived.  A detour leaves from the tip of the stroke that was just drawn,
# so that stroke's own ink is legitimately right there -- enforcing clearance
# against it would wall the route in before it takes a single step
# (confirmed: doing so fails every loop-back outright, including the
# previously-working single-level `+++[-].`).  Deliberately as small as
# possible: one cell is enough to let the route step off its own stroke, and
# anything larger silently disables `_CLEARANCE` over a wide area (at
# `_UNIT`, it would waive clearance within 400 raster px of every departure
# point, which is most of a small drawing).
_DEPARTURE_EXEMPT = 1


def _clear_at(
    p: tuple[int, int],
    occupied: set[tuple[int, int]],
    exempt_origin: tuple[int, int] | None = None,
) -> bool:
    """Whether ``p`` and every pixel within :data:`_CLEARANCE` of it is free.

    See :data:`_CLEARANCE`: a detour that merely avoids overlapping existing
    ink can still run flush against it, which the extractor's band probe
    cannot tell apart from a real junction.  Within
    :data:`_DEPARTURE_EXEMPT` of ``exempt_origin`` (the route's own start),
    only ``p`` itself must be free -- see that constant for why.
    """
    if exempt_origin is not None:
        dy = abs(p[0] - exempt_origin[0])
        dx = abs(p[1] - exempt_origin[1])
        if max(dy, dx) <= _DEPARTURE_EXEMPT:
            return p not in occupied
    for dy in range(-_CLEARANCE, _CLEARANCE + 1):
        for dx in range(-_CLEARANCE, _CLEARANCE + 1):
            if (p[0] + dy, p[1] + dx) in occupied:
                return False
    return True


def _edge_clear(
    p: tuple[int, int],
    direction: tuple[int, int],
    occupied: set[tuple[int, int]],
    exempt_origin: tuple[int, int] | None = None,
) -> bool:
    """Whether every pixel strictly between ``p`` and ``p + _UNIT*direction`` is clear.

    "Clear" means clear *with clearance* -- see :data:`_CLEARANCE` for why
    simple non-overlap lets two detours rasterize into one indistinguishable
    2px-wide ribbon.
    """
    dy, dx = direction
    y, x = p
    for _ in range(_UNIT):
        y, x = y + dy, x + dx
        if not _clear_at((y, x), occupied, exempt_origin):
            return False
    return True


def _astar(
    start: tuple[int, int],
    aim: tuple[int, int],
    step: int,
    bounds: tuple[int, int, int, int],
    edge_clear: object,
    *,
    is_goal: object,
    exempt_goal: object,
    avoid: set[tuple[int, int]] | None = None,
) -> list[tuple[int, int]] | None:
    """Search 4-directionally from ``start`` toward ``aim`` on a ``step`` grid.

    ``edge_clear(p, direction)`` decides whether the edge from ``p`` one
    ``step`` in ``direction`` is passable.  ``aim`` only drives the search's
    distance heuristic (Manhattan distance to it); the actual stopping
    condition is ``is_goal(node)``, which lets a caller accept more than one
    exact node as success -- see below for why the coarse pass needs that.
    ``bounds`` is ``(lo_y, hi_y, lo_x, hi_x)``, the inclusive region node
    coordinates must stay within.  Returns the node path (inclusive of both
    ends), or ``None`` if exhausted without satisfying ``is_goal`` within
    :data:`_MAX_ROUTE_SEARCH` explored nodes.  Shared by both the coarse
    (:data:`_UNIT`-pixel step) and fine (1-pixel step) passes
    :func:`_route_legs` runs -- the two differ only in step size, edge
    validity, and goal test.

    ``exempt_goal(node)`` controls whether arriving at a node satisfying
    ``is_goal`` skips the edge-clear check for that final step -- ``True``
    only for the real merge point (which is real ink by construction, see
    :func:`_layout`).  The coarse pass's own *ideal* waypoint (the rounded
    approximation of the real target -- see :func:`_route_legs`) must never
    get this exemption: it can coincide with a genuinely occupied pixel by
    pure coordinate coincidence (confirmed: a coarse waypoint landed exactly
    on an unrelated fork's own branch vertex in a real nested-loop program,
    and exempting it let the coarse path cross straight through real ink
    that any other node would have been correctly blocked by).  Accepting
    *any* node within one coarse step of that ideal point as the coarse
    pass's goal (rather than forcing the single exact point, which is not
    always reachable even when a nearby point clearly is) is what
    :func:`_route_legs` actually uses ``is_goal`` for.

    ``avoid`` is a set of cells that cost extra to enter but are not
    obstacles: each ``avoid`` node stepped onto adds :data:`_AVOID_PENALTY`
    to the path cost.  See :func:`_route_pending` for what these are (later
    detours' departure neighborhoods) and why they must be costed rather
    than blocked -- a hard block turns "keep off my doorstep if you can"
    into a wall that can seal the only lane another route has.
    """
    import heapq
    from collections.abc import Callable
    from typing import cast

    is_clear = cast(Callable[[tuple[int, int], tuple[int, int]], bool], edge_clear)
    goal = cast(Callable[[tuple[int, int]], bool], is_goal)
    exempt = cast(Callable[[tuple[int, int]], bool], exempt_goal)
    dirs = [(-1, 0), (1, 0), (0, 1), (0, -1)]
    ay, ax = aim
    lo_y, hi_y, lo_x, hi_x = bounds

    def h(p: tuple[int, int]) -> int:
        return (abs(p[0] - ay) + abs(p[1] - ax)) // step

    frontier: list[tuple[int, int, tuple[int, int]]] = [(h(start), 0, start)]
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    cost_so_far: dict[tuple[int, int], int] = {start: 0}
    explored = 0

    while frontier:
        _, cost, cur = heapq.heappop(frontier)
        if goal(cur):
            path = [cur]
            while came_from[path[-1]] is not None:
                path.append(came_from[path[-1]])  # type: ignore[arg-type]
            path.reverse()
            return path
        explored += 1
        if explored > _MAX_ROUTE_SEARCH:
            return None
        for dy, dx in dirs:
            nxt = (cur[0] + dy * step, cur[1] + dx * step)
            if not (lo_y <= nxt[0] <= hi_y and lo_x <= nxt[1] <= hi_x):
                continue
            if not (goal(nxt) and exempt(nxt)) and not is_clear(cur, (dy, dx)):
                continue
            new_cost = cost + step
            if avoid is not None and nxt in avoid:
                new_cost += _AVOID_PENALTY
            if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                cost_so_far[nxt] = new_cost
                came_from[nxt] = cur
                heapq.heappush(frontier, (new_cost + h(nxt), new_cost, nxt))
    return None


def _leg_cells(
    start: tuple[int, int], legs: list[tuple[tuple[int, int], int]]
) -> list[tuple[int, int]]:
    """Every grid cell a run of ``legs`` walks through, starting from ``start``."""
    cells = [start]
    y, x = start
    for (dy, dx), length in legs:
        for _ in range(length):
            y, x = y + dy, x + dx
            cells.append((y, x))
    return cells


def _self_approaches(cells: list[tuple[int, int]]) -> bool:
    """Whether a route ever runs within :data:`_CLEARANCE` of its own earlier self.

    A route is planned against ``occupied`` as it stood *before* the route
    existed, and A* never adds its own in-progress cells to that set -- so
    nothing in the search stops a detour from doubling back and running flush
    alongside a leg it laid down earlier in the very same route.  That is a
    real failure, not a theoretical one: it is what remained of the
    nested-loop regression after :data:`_CLEARANCE` fixed the *between*-detour
    case.  Confirmed by per-stroke attribution on ``++[>++[>+<-]<-]>>.``,
    where all three arms of the spurious T-junction that broke execution
    belonged to one single stroke -- the inner loop's own 530-cell detour
    touching itself.

    Only cells far enough apart *along* the route are compared: consecutive
    cells are trivially adjacent, and a legitimate 90-degree corner puts
    cells a few steps apart near each other by construction.  Anything beyond
    that window running within clearance is the route folding back onto
    itself.
    """
    window = 2 * (_CLEARANCE + 1) + 1
    seen: dict[tuple[int, int], int] = {}
    for i, (y, x) in enumerate(cells):
        for dy in range(-_CLEARANCE, _CLEARANCE + 1):
            for dx in range(-_CLEARANCE, _CLEARANCE + 1):
                j = seen.get((y + dy, x + dx))
                if j is not None and i - j > window:
                    return True
        seen[(y, x)] = i
    return False


def _path_to_legs(path: list[tuple[int, int]]) -> list[tuple[tuple[int, int], int]]:
    """Collapse a node path into ``(direction, pixel_length)`` runs."""
    legs: list[tuple[tuple[int, int], int]] = []
    for i in range(1, len(path)):
        dy, dx = path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]
        length = max(abs(dy), abs(dx))
        direction = (
            0 if dy == 0 else (1 if dy > 0 else -1),
            0 if dx == 0 else (1 if dx > 0 else -1),
        )
        if legs and legs[-1][0] == direction:
            legs[-1] = (direction, legs[-1][1] + length)
        else:
            legs.append((direction, length))
    return legs


def _route_legs(
    start: tuple[int, int],
    target: tuple[int, int],
    occupied: set[tuple[int, int]],
    padding: int,
    avoid: set[tuple[int, int]] | None = None,
) -> list[tuple[tuple[int, int], int]]:
    """Route from ``start`` to ``target`` around ``occupied``, cardinal-only.

    Only the 4 cardinal directions are ever used, never a diagonal step:
    :mod:`extract`'s ``classify_ops`` identifies a real ``+``/``-`` opcode by
    a single 45-degree diagonal jog of any length between two straight runs
    (see its ``_FIXED_SIGNATURES``/lone-diagonal fallback), so a detour leg
    that happens to be diagonal risks being misread as an extra, spurious
    opcode call -- confirmed to actually happen with an earlier
    diagonal-then-straight detour, which added a phantom ``-`` call to a
    synthetic loop test.  Every cardinal-to-cardinal turn is 0, 90, or 180
    degrees, which no opcode signature matches, so a purely 4-directional
    path is unambiguous regardless of shape.

    Two passes, not one: a pixel-exact A* over the whole distance was tried
    first and rejected on performance grounds -- confirmed directly on a real
    boolean-generator brainfuck program's compiled decision tree, where a
    genuinely reachable target ~500px away timed out the search entirely
    rather than being found, since a pixel grid explores ``_UNIT**2`` more
    nodes than necessary to cover the same distance.  The fix: a *coarse*
    A* first, stepping by whole :data:`render._UNIT` grid units (matching the
    scale every straight run in a Line drawing already uses) with each edge
    validated pixel-by-pixel (:func:`_edge_clear`) so coarse safety is exactly
    equivalent to fine safety for that edge -- covering the bulk of the
    distance at ``_UNIT**2`` fewer explored nodes.  The coarse grid is
    anchored at ``start`` (so ``start`` always lands exactly on it) and aimed
    at the coarse node nearest ``target``, which will not generally *be*
    ``target`` exactly; a second, fine (1-pixel step) A* then covers the
    short residual gap (at most one grid unit per axis), landing exactly.
    When the split itself is what fails -- the coarse lattice cannot thread a
    corridor the drawing genuinely contains -- a pixel-exact A* over the same
    padded bounds runs as a last resort; see the recovery comment in the body
    for the measured case that requires it.

    ``target`` is reachable even though it is itself real ink (the merge
    point sits inside an existing stroke's segment by construction -- see
    :func:`_layout`) -- only cells strictly between ``start`` and ``target``
    are required to be clear, matching the same "goal is the one exception"
    rule an earlier cell-grid attempt used.  The search is confined to the
    bounding box of ``start``/``target`` expanded by ``padding`` pixels on
    every side (an unbounded search is impractical -- confirmed directly: a
    plain flood fill, independent of this module's own A*, from a real
    failing case's start pixel did not finish within two minutes on a huge,
    mostly-empty canvas); :func:`_close_loop` retries with a larger
    ``padding`` if this raises :class:`ValueError`.

    Returns collapsed ``(direction, length)`` legs (consecutive same-
    direction runs merged) rather than a raw pixel list, so the caller can
    walk it with a handful of ``cursor.advance`` calls, matching every other
    stroke in a Line drawing's straight-run style.
    """
    ty, tx = target
    lo_y, hi_y = min(start[0], ty) - padding, max(start[0], ty) + padding
    lo_x, hi_x = min(start[1], tx) - padding, max(start[1], tx) + padding
    bounds = (lo_y, hi_y, lo_x, hi_x)

    def coarse_clear(p: tuple[int, int], direction: tuple[int, int]) -> bool:
        return _edge_clear(p, direction, occupied, start)

    dy, dx = ty - start[0], tx - start[1]
    rounded = (
        start[0] + round(dy / _UNIT) * _UNIT,
        start[1] + round(dx / _UNIT) * _UNIT,
    )
    # `rounded` is only ever an *approximation* of `target` (see docstring),
    # not itself guaranteed clear -- it can coincide exactly with genuinely
    # occupied ink by pure coordinate coincidence (confirmed: a rounded
    # waypoint landed exactly on an unrelated fork's own branch vertex in a
    # real nested-loop program).  Accepting `rounded` *or* any of its 4
    # immediate coarse neighbors as the goal (rather than forcing exactly
    # `rounded`, which is not always reachable even when a neighbor clearly
    # is -- confirmed on the same program, where nudging to a single fixed
    # neighbor still failed) lets A* itself find whichever candidate the
    # occupied geometry actually permits; the fine pass below then covers
    # however much residual gap to the real `target` whichever candidate
    # won leaves (at most one grid unit further per axis than `rounded`
    # alone would have).
    coarse_candidates = {rounded}
    for cdy, cdx in ((-1, 0), (1, 0), (0, 1), (0, -1)):
        coarse_candidates.add((rounded[0] + cdy * _UNIT, rounded[1] + cdx * _UNIT))

    def never_exempt(p: tuple[int, int]) -> bool:
        del p
        return False

    def fine_clear(p: tuple[int, int], direction: tuple[int, int]) -> bool:
        nxt = (p[0] + direction[0], p[1] + direction[1])
        return _clear_at(nxt, occupied, start)

    def fine_goal(p: tuple[int, int]) -> bool:
        return p == target

    def exempt_final(p: tuple[int, int]) -> bool:
        return p == target

    # The coarse pass stops at whichever candidate is *cheapest from the
    # start*, which is not necessarily one the fine pass can work from.
    # Measured on the depth-4 program `+[>+[>+[>+[>+<-]<-]<-]<-]>>>>.` after
    # corridor-reserving layout (see :func:`_arm_spacing`) had made its routes
    # exist at all: the start's own column happened to align with the
    # candidate one coarse step *left* of `rounded`, so the coarse pass ran 40
    # cells straight up, stopped there -- on the wrong side of a wall -- and
    # the fine pass then did the entire remaining journey at pixel step,
    # coming back down through the coarse leg's own cells (one cell was
    # visited twice).  `_close_loop` correctly rejects such a route as
    # self-approaching, and since every offset failed the same way, the render
    # failed even though clear pixel routes existed (a full pixel A* from the
    # same start reached 11 approach points in ~0.05s each, none folding).
    #
    # Two recoveries, tried in order, both leaving the success path
    # untouched -- a route that succeeds on the first candidate routes
    # identically to before they existed, so only failures can change, into
    # recoveries:
    #
    # 1. When the fine pass fails outright or the combined path folds back on
    #    itself, exclude the candidate the coarse pass reached and re-run it
    #    (at most 5 candidates exist, so this terminates).  This is the cheap
    #    rescue for long hauls, where a full pixel search is the thing the
    #    two-pass split exists to avoid.
    # 2. When no coarse candidate yields a clean route at all, fall back to a
    #    single pixel-exact A* over the same padded bounds.  A corridor
    #    reserved by :func:`_arm_spacing` is `_GOTO_CORRIDOR` = 3 cells wide
    #    -- wide enough for exactly one clear line -- and a coarse edge is 20
    #    consecutive clear cells anchored to the start's own lattice, so the
    #    coarse pass can only thread a corridor by alignment luck; the pixel
    #    pass threads it by construction.  Measured on the same depth-4
    #    program: after recovery 1 still found nothing (no second candidate
    #    was coarse-reachable), this pass routed it in well under a second.
    #    `_MAX_ROUTE_SEARCH` bounds the cost like every other attempt.
    #
    # (`_close_loop` still runs its own diagonal-inclusive `_self_approaches`
    # check on top; the checks here cannot see the diagonal.)
    excluded: set[tuple[int, int]] = set()
    for _ in range(len(coarse_candidates)):

        def coarse_goal(p: tuple[int, int]) -> bool:
            return p in coarse_candidates and p not in excluded

        # The coarse pass penalizes only its own 20-cell *nodes* landing in
        # `avoid`, so a coarse edge can cross a small avoid region with both
        # endpoints outside it, unpenalized.  Accepted: the crowded regions
        # where doorsteps live route via the per-cell pixel passes anyway
        # (measured -- that is what the fallback below exists for).
        coarse_path = _astar(
            start,
            rounded,
            _UNIT,
            bounds,
            coarse_clear,
            is_goal=coarse_goal,
            exempt_goal=never_exempt,
            avoid=avoid,
        )
        if coarse_path is None:
            break
        coarse_target = coarse_path[-1]

        fine_path = _astar(
            coarse_target,
            target,
            1,
            bounds,
            fine_clear,
            is_goal=fine_goal,
            exempt_goal=exempt_final,
            avoid=avoid,
        )
        if fine_path is None:
            excluded.add(coarse_target)
            continue

        legs = _path_to_legs(coarse_path + fine_path[1:])
        if _self_approaches(_leg_cells(start, legs)):
            excluded.add(coarse_target)
            continue
        return legs

    full_path = _astar(
        start,
        target,
        1,
        bounds,
        fine_clear,
        is_goal=fine_goal,
        exempt_goal=exempt_final,
        avoid=avoid,
    )
    if full_path is not None:
        legs = _path_to_legs(full_path)
        if not _self_approaches(_leg_cells(start, legs)):
            return legs

    raise ValueError(
        "no clear route found for the loop-back detour within the "
        "current search padding -- the drawing may be too densely "
        "packed for this program's loop nesting"
    )


# Starting search padding (pixels) for `_close_loop`'s first attempt, and
# how many times it doubles before giving up -- kept small at first so the
# common case (a nearby, unobstructed reconnection) resolves in a small,
# fast search rather than always paying for a search of the whole drawing's
# extent up front.  4 doublings from 4*_UNIT covers well past any real
# fixture or generated program tried here before the per-attempt node cap
# (`_MAX_ROUTE_SEARCH`) would matter at that padding.
_INITIAL_PADDING = 4 * _UNIT
_MAX_PADDING_DOUBLINGS = 6


def _close_loop(
    cursor: _Cursor,
    stem_start: tuple[int, int],
    stem_heading: tuple[int, int],
    occupied: set[tuple[int, int]],
    avoid: set[tuple[int, int]] | None = None,
) -> None:
    """Route from ``cursor``'s current point onto some point along a stem.

    ``stem_start``/``stem_heading`` describe the straight run leading into
    some ``?`` node's own branch point (recorded by :func:`_layout`); the
    reconnection lands strictly *inside* that run, not the fork's own vertex
    -- see the comment above :func:`_route_legs` for why.  Tries every whole-
    unit offset from 1 to :data:`_STEM_LEN` - 1 in turn (skipping the two
    ends, which are real vertices, not interior points) at a given search
    padding, routing to whichever is reachable first via :func:`_route_legs`
    -- a single fixed offset (e.g. always the exact midpoint) can end up
    walled in on every side by unrelated ink drawn elsewhere after this stem,
    which happens in practice in a dense decision tree (confirmed on a real
    boolean-generator brainfuck program's compiled output).

    All offsets are tried at the current padding before the padding itself
    grows (see :data:`_INITIAL_PADDING`/:data:`_MAX_PADDING_DOUBLINGS`): most
    reconnections are found nearby, so this keeps the common case cheap and
    only pays for a wider search when every offset genuinely needs more room
    to route around.

    ``avoid`` is passed through to the router as soft cost (see
    :func:`_astar` and :func:`_route_pending`); an approach point sitting
    *inside* an avoid region is skipped outright, since landing the detour's
    final corner on a later detour's doorstep defeats the region's purpose.
    Every clearance check here stays against real ``occupied`` ink only.
    """
    hy, hx = stem_heading
    targets = [
        (stem_start[0] + hy * offset, stem_start[1] + hx * offset)
        for offset in range(1, _STEM_LEN)
    ]
    padding = _INITIAL_PADDING
    errors: list[str] = []
    for _ in range(_MAX_PADDING_DOUBLINGS + 1):
        for target in targets:
            for approach, diagonal in _approach_points(target, stem_heading):
                # Route cardinally to the diagonal approach point, then take
                # the final diagonal leg onto the stem by hand -- see
                # `_approach_points` for why the last leg cannot be cardinal.
                # The approach point is an ordinary detour corner, so it needs
                # full clearance; the diagonal's own pixels only need to be
                # free, since by the last step or two they are deliberately
                # closing on the stem's ink and clearance cannot hold there.
                if not _clear_at(approach, occupied):
                    continue
                if avoid is not None and approach in avoid:
                    continue
                if any(
                    (
                        approach[0] + diagonal[0] * i,
                        approach[1] + diagonal[1] * i,
                    )
                    in occupied
                    for i in range(1, _DIAGONAL_APPROACH)
                ):
                    continue
                try:
                    legs = _route_legs(
                        (cursor.y, cursor.x), approach, occupied, padding, avoid
                    )
                except ValueError as exc:
                    errors.append(str(exc))
                    continue
                # A* plans against `occupied` as it stood before this route
                # existed, so it cannot see the route's own cells -- reject a
                # route that folds back alongside itself and try the next
                # candidate instead (see `_self_approaches`).
                full = [*legs, (diagonal, _DIAGONAL_APPROACH)]
                if _self_approaches(_leg_cells((cursor.y, cursor.x), full)):
                    errors.append("route folded back onto itself")
                    continue
                for direction, length in legs:
                    cursor.advance(direction, length)
                cursor.advance(diagonal, _DIAGONAL_APPROACH)
                if (cursor.y, cursor.x) != target:  # pragma: no cover - geometry guard
                    raise AssertionError(
                        f"loop-back detour landed at {(cursor.y, cursor.x)}, "
                        f"expected {target}"
                    )
                return
        padding *= 2
    raise ValueError(
        "no clear route found for the loop-back detour at any offset along "
        "the target stem, even at maximum search padding -- the drawing may "
        f"be too densely packed for this program's loop nesting ({errors[-1]})"
    )


# Length (in grid units) of the stem `_layout` walks into a `?` node's own
# branch point.  `_close_loop` tries every whole-unit offset from 1 to this
# minus 1 as a candidate reconnection point (see its own docstring for why
# more than one candidate is needed), so this is also how many candidates
# a loop-back gets to find a clear one -- long enough in practice for every
# fixture and generated program tried, including a real boolean-generator
# brainfuck program's dense compiled decision tree.
_STEM_LEN = 10


# How far back along the detour the final *diagonal* approach leg starts, in
# *grid cells* (so 6 here is 120 raster pixels, comfortably longer than
# `lattice.star`'s own 15px probe).  See `_approach_points` for why the last
# leg must be diagonal rather than cardinal like the rest of the route.
#
# Being *longer* than the probe is what makes this work, not shorter: the
# probe must find a full, unbroken band segment along the diagonal so the
# merge point lights that third direction and `lattice._classify` reads
# `"merge"`.  A diagonal too short to fill the probe would leave the merge
# point reading only the stem's own two directions -- an ordinary
# `"straight"` bend, which the walker would sail straight through, continuing
# down the stem instead of stopping the stroke as a leaf.
_DIAGONAL_APPROACH = 6


def _approach_points(
    target: tuple[int, int], stem_heading: tuple[int, int]
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Candidate ``(approach_start, diagonal)`` pairs for landing on ``target``.

    The detour's final step onto the stem must arrive *diagonally*, not
    cardinally, and this is load-bearing rather than cosmetic.  Everything
    :func:`_route_legs` draws is cardinal-only (see its docstring -- a
    diagonal detour leg risks being misread as a ``+``/``-`` kink), and the
    stem being landed on is itself a cardinal run, so a cardinal final
    approach is necessarily *perpendicular* to the stem.  A perpendicular
    touch-down onto a straight run lights exactly the arrival direction plus
    the stem's own two directions -- which is the arrived-from direction plus
    the pair perpendicular to it, i.e. precisely the T-branch signature
    ``lattice._classify`` calls a real ``"fork"``.  The extractor then reads
    the loop-back merge as a conditional turn, and :mod:`simulate` executes
    the reconnection as a branch instead of a jump.

    Arriving diagonally lights that same stem pair plus a direction that is
    *not* perpendicular to it, which ``_classify`` correctly calls
    ``"merge"`` -- stopping the stroke as a leaf, which is exactly what
    :func:`simulate._compile`'s ``find_merge`` expects to rescue into a
    ``goto``.  This also matches how the wiki's own hand-drawn fixtures
    reconnect (``addition.png``'s loop-body arm arrives at its stem on a
    diagonal), which is why merge classification worked there and why this
    only ever broke on rendered output.

    Both diagonals leaving the target on each side of the stem are offered,
    since either may be walled in by unrelated ink; the caller tries them in
    turn.  Each pair is ``(approach_start, diagonal_direction)`` where
    ``approach_start`` is a clear cardinal-routable point and stepping
    ``_DIAGONAL_APPROACH`` times along ``diagonal_direction`` from it lands
    exactly on ``target``.
    """
    hy, hx = stem_heading
    pairs = []
    for side in (1, -1):
        py, px = _turn_right((hy, hx))
        py, px = py * side, px * side
        # Step *back* along the stem and out to one side, so the return trip
        # is a diagonal that lands on the target from off the stem's line.
        for along in (1, -1):
            diagonal = (-hy * along - py, -hx * along - px)
            start = (
                target[0] - diagonal[0] * _DIAGONAL_APPROACH,
                target[1] - diagonal[1] * _DIAGONAL_APPROACH,
            )
            pairs.append((start, diagonal))
    return pairs


# Minimum gap (grid units) a fork arm runs before laying out its content, and
# the safety margin added on top of whatever :func:`_arm_spacing` measures.
#
# This used to be the whole story: arms were sized `_BRANCH_SPACING *
# 2 ** remaining_depth` from a `_fork_depth` helper that counted how many more
# nested `?` forks an arm still had to fit.  That geometric halving encoded a
# real insight -- every fork turns its children 90 degrees, so a *grand*child
# turns back toward the original heading and overshoots its grandparent's axis
# if its arm is longer than the distance back to it, which is why arms must
# shrink with depth rather than grow (an earlier version grew them, and
# scaling it up 10x reproduced the identical "extraction left N pixels
# unaccounted for" failure, since growing rather than the absolute scale was
# the bug).
#
# But counting forks is a proxy for the thing that actually matters, and a
# poor one: it is blind to how much ink a subtree lays down, so two programs
# with identical branching structure and very different content got identical
# arms, and a fork's two arms got the same length even when one held 4 ops and
# the other 14.  :func:`_arm_spacing` now measures each subtree's real extent
# instead (see :func:`_subtree_extent`), which subsumes the H-tree insight
# exactly: "how far does this subtree reach back toward the trunk" is the
# quantity the halving was approximating, and measuring answers it directly.
#
# What remains here is a floor, not a scaling law -- a subtree that reaches
# back barely at all still needs sibling arms not to start flush against the
# trunk.  5 is deliberately small: it was lowered from 20 when a sweep showed
# every program in all three suites still extracting and executing correctly
# at 20/8/5/3/2/1, and with extent-based spacing carrying the real work it is
# no longer the constant that decides whether a drawing fits.
_BRANCH_SPACING = 5


# Width, in grid cells, of the routing corridor one loop-back detour needs to
# pass an arm -- see :func:`_arm_spacing`, which reserves one of these per
# `goto` beneath the arm.
#
# This is not a chosen number, which matters: a fixed `_GOTO_CHANNEL` constant
# was tried during the depth-3 work and removed precisely because it was
# guessing at a quantity nothing had measured.  It is the swath a routed
# detour actually blocks, and the router itself defines that: one cell of the
# detour's own stroke, plus `_CLEARANCE` of mandated gap on either side (see
# :func:`_clear_at` -- a route is rejected unless every cell within
# `_CLEARANCE` is free, so a detour makes a `1 + 2*_CLEARANCE` band unusable,
# not merely its own line).  Written as the expression rather than its value
# so that changing `_CLEARANCE` moves the corridors with it.
_GOTO_CORRIDOR = 1 + 2 * _CLEARANCE


# Memoized `_subtree_extent` results for one `render()` call, keyed by node id.
#
# Measuring is a full dry-run `_layout` of the subtree, and every fork asks
# about subtrees that themselves contain forks -- so without memoization the
# work is exponential in nesting depth, not merely repeated.  That is not a
# theoretical cost: an unmemoized version of this stalled outright on a
# depth-3 program (no output at all after two minutes, where the memoized one
# finishes in well under a second).
#
# Cleared at the start of every `render()` rather than living as a permanent
# global, because `id()` is only unique among *live* objects: a `Node` freed
# between two renders can have its address reused by an unrelated node in the
# next one, which a persistent cache would answer with the dead node's extent.
# Scoping to a single render means every measured node is reachable from that
# render's own root for the whole time the cache exists.
_EXTENT_CACHE: dict[int, tuple[int, int, int, int]] = {}


def _count_gotos(node: Node | None, seen: set[int] | None = None) -> int:
    """How many loop-backs ``node``'s subtree contains, each needing a corridor.

    Walks the same `.next`/`.zero`/`.nonzero` edges :func:`_subtree_extent`
    does, and stops at a `goto` rather than following it (it cycles back to an
    ancestor -- see :class:`Node`'s docstring).  Both arms of a `?` are summed:
    every `goto` anywhere beneath this arm eventually routes a detour that has
    to get *past* this arm, so each one is a separate crossing the arm's own
    spacing must survive -- see :func:`_arm_spacing`.
    """
    if seen is None:
        seen = set()
    total = 0
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        if node.goto is not None:
            return total + 1
        if node.op == "?":
            return (
                total + _count_gotos(node.zero, seen) + _count_gotos(node.nonzero, seen)
            )
        node = node.next
    return total


def _subtree_extent(node: Node | None) -> tuple[int, int, int, int]:
    """Measure the bounding box ``node``'s subtree actually draws.

    Returns ``(min_forward, max_forward, min_lateral, max_lateral)`` in grid
    units, relative to the subtree's entry point, as if it were laid out
    heading "forward" -- a caller rotates it onto whatever heading the arm
    really runs.

    This exists because sizing a fork's arms by *fork count* alone -- what the
    removed `_fork_depth` did, feeding `_BRANCH_SPACING * 2**remaining` -- is
    blind to how much ink a subtree lays down.  Measured directly: the two
    depth-3 programs `+[>+[>+[>+<-]<-]<-]>>>.` and
    `++[>++[>++[>+<-]<-]<-]>>>.` produce *identical* spacing at every fork
    (40/20/10 units) despite carrying different op counts in every arm, and
    the heavier one is exactly the case that exhausts `_close_loop`'s router.
    A fork's two arms are sized identically for the same reason, even when
    wildly asymmetric (the depth-0 fork above has 4 ops on one arm and 14 on
    the other).  Extent is the quantity the layout actually needs, so it is
    now the quantity measured.

    Deliberately runs the *real* :func:`_layout` against a scratch cursor
    rather than reimplementing its geometry: a parallel size-estimating walk
    would drift from the code that actually draws, and then every extent it
    reports is a quiet lie.  The scratch cursor carries no `occupied` set,
    which is exactly what makes `_layout` treat a `goto` as terminal (see its
    ``measuring`` parameter) -- a detour cannot be routed in isolation anyway,
    since routing needs the whole drawing's occupancy -- see
    :func:`_route_pending`, which routes every detour after layout finishes.
    """
    if node is None:
        return (0, 0, 0, 0)
    cached = _EXTENT_CACHE.get(id(node))
    if cached is not None:
        return cached
    scratch = _Cursor(0, 0, _FORWARD)
    _layout(node, scratch, measuring=True)
    points = [p for stroke in scratch.strokes for p in stroke] or [(0, 0)]
    ys = [p[0] for p in points]
    xs = [p[1] for p in points]
    extent = (min(ys), max(ys), min(xs), max(xs))
    _EXTENT_CACHE[id(node)] = extent
    return extent


@dataclass
class _Pending:
    """One loop-back detour whose routing is deferred to `render()`'s 2nd phase.

    Holds the cursor sitting at the loop body's end (already flushed, so its
    own ink is in `occupied`), the ``?`` node the ``goto`` targets, and the
    fork-nesting ``depth`` the jump was found at -- see
    :func:`_route_pending` for what the depth orders.
    """

    cursor: _Cursor
    target: Node
    depth: int


def _route_pending(
    pending: list[_Pending],
    entries: dict[int, tuple[tuple[int, int], tuple[int, int]]],
    occupied: set[tuple[int, int]],
) -> list[list[tuple[int, int]]]:
    """Route every deferred loop-back detour, outermost fork first.

    Routing a detour the moment its ``goto`` is reached -- what `_layout` used
    to do -- is an ordering bug, not a spacing one.  A detour routes against
    `occupied` *as it stands mid-layout*, so it can only avoid ink already
    drawn; every stroke laid out afterwards is free to march straight through
    the corridor it just took, and nothing ever checks.  No amount of extra
    arm spacing fixes that, because the collision is with geometry that did
    not exist when the route was chosen.  (An earlier attempt here reserved a
    fixed routing channel per loop-carrying arm, which is a guess at a
    quantity this ordering makes unknowable.)

    Deferring every detour until all fixed geometry exists means each one
    routes against the *complete* drawing, plus every detour already routed
    before it -- so `_CLEARANCE` and `_self_approaches` mean what they say.
    This is the two-phase layout ``WIP.md`` proposed ("place all fixed
    geometry, then route every ``goto`` outermost-first against full
    occupancy").

    Outermost-first (shallowest fork depth) matters because an outer loop's
    detour has to travel around everything its nested inner loops occupy,
    while an inner one is comparatively local: letting the constrained route
    choose first leaves the flexible one to work around it, rather than the
    reverse.
    """
    strokes: list[list[tuple[int, int]]] = []
    order = sorted(pending, key=lambda p: p.depth)
    for i, entry in enumerate(order):
        stem_start, stem_heading = entries[id(entry.target)]
        # Every detour not yet routed will have to *leave* its own departure
        # point, so no earlier route should squat on it.  Without this, an
        # earlier route is free to run directly across a later departure
        # point's doorstep -- A* takes the shortest clear path, which hugs
        # existing ink at exactly `_CLEARANCE`, and a departure point sits at
        # the tip of drawn ink by construction.  Measured on the depth-4
        # program: the depth-3 detour's route boxed the first depth-4 detour's
        # start into an 8-cell pocket (out of a ~28000-cell canvas), with
        # attribution showing that one route alone responsible.
        #
        # The `_GOTO_CORRIDOR`-radius block around each future start is
        # *costed*, not blocked (see :data:`_AVOID_PENALTY`): passing it as
        # hard occupancy was tried and failed the same program one detour
        # later, because the two depth-4 doorsteps sit a column apart and the
        # first's only lane to its stem runs straight through the second's
        # blocked ring -- 152 reachable cells with the ring hard, 1086
        # without.  A finite cost keeps doorsteps clear whenever a clear
        # alternative exists and, when none does, lets the route cross on the
        # shortest chord.  Measured on the shipped path: three of the four
        # routes trespass zero avoid cells, and the boxed-in one pays exactly
        # a 7-cell chord through the last doorstep's region, passing at
        # distance 3 from its start -- which still escapes, since the chord
        # crosses a side its own route never needs.  The regions never enter
        # the real `occupied` set, so once a detour's own turn comes its
        # reservation is gone and its route is checked only against real ink.
        avoid: set[tuple[int, int]] = set()
        for later in order[i + 1 :]:
            sy, sx = later.cursor.y, later.cursor.x
            for dy in range(-_GOTO_CORRIDOR, _GOTO_CORRIDOR + 1):
                for dx in range(-_GOTO_CORRIDOR, _GOTO_CORRIDOR + 1):
                    avoid.add((sy + dy, sx + dx))
        # Only the strokes *this* call adds: the cursor already carries the
        # loop body's own strokes, which the fork that spawned it collected
        # into the drawing when `_layout` returned.  Extending with the whole
        # list would hand every loop body back a second time.
        before = len(entry.cursor.strokes)
        _close_loop(entry.cursor, stem_start, stem_heading, occupied, avoid)
        entry.cursor.finish()
        strokes.extend(entry.cursor.strokes[before:])
    return strokes


def _arm_spacing(arm: Node | None) -> int:
    """How far a fork arm runs before laying out ``arm``'s own content.

    The arm must run far enough that everything ``arm`` draws clears the
    fork's own trunk axis -- the line the stem arrived along, which the two
    arms leave perpendicular to.  A subtree that turns back toward that axis
    (every nested fork does: its children turn 90 degrees, so its
    *grand*children turn back parallel to the original heading) reaches some
    measured distance back along it, and the arm has to be at least that long
    plus a margin, or the subtree overshoots and crosses the trunk.

    That distance comes straight from a measured extent rather than the old
    `2 ** remaining` guess at it.  The guess was not merely imprecise: it
    could not distinguish two programs of identical branching structure
    carrying different amounts of ink, and gave a fork's two arms the same
    length even when one held 4 ops and the other 14 (see
    :func:`_subtree_extent`).

    Sibling separation needs no term of its own, which is worth stating since
    an intermediate version of this function had one and it was actively
    harmful.  The two arms leave the fork in opposite directions along one
    axis, and `reach_back` already puts each subtree's *entire* bounding box
    strictly on its own side of the trunk -- so the two boxes are separated by
    at least twice the margin automatically.  The arms' lateral spans spread
    along the perpendicular axis, where the boxes cannot meet at all.  Adding
    a lateral term regardless double-counted it into both arms and, because
    each fork's measured span then contained its children's already-inflated
    spacing, amplified geometrically with depth: a depth-3 program's outermost
    arm measured 149 units laterally and rendered at 7760x3800 (vs ~1600
    here).

    :data:`_BRANCH_SPACING` is the floor and the safety margin, so a subtree
    that reaches back barely at all still gets a real gap.

    On top of that, an arm reserves one :data:`_GOTO_CORRIDOR` per ``goto``
    beneath it, which is what makes nesting past depth 3 drawable.  The reason
    is measured rather than assumed (the depth-4 failure was instrumented
    before being characterised -- see ``WIP.md``): detours are far bigger than
    the program they serve, so the binding constraint is not fixed geometry at
    all but *earlier detours*.  On `+[>+[>+[>+[>+<-]<-]<-]<-]>>>>.`, a flood
    fill from the third detour's own departure point reached 5% of the canvas,
    and attribution showed a single earlier detour responsible: with fixed
    geometry alone that same point reached 97%.  With every inner arm sitting
    at the `_BRANCH_SPACING` floor of 5, one detour crossing a gap blocks
    `_GOTO_CORRIDOR` of it and seals the region behind it into a pocket.

    Reserving `n * _GOTO_CORRIDOR` makes a gap survive the `n` crossings that
    can actually occur and still leave a corridor's worth of room for the
    passage itself.  The reservation is not a routing *preference* -- A* takes
    whatever is shortest and clear, and a detour may still sweep the long way
    around; it works by leaving the drawing connected once it does.

    The term is deliberately added to the arm being measured, once, and only
    for arms that carry a `goto`: an earlier version of this function had a
    lateral term applied to both arms regardless, which double-counted into
    each fork's measured span and so amplified geometrically with depth (see
    above).  Here a goto-free arm gets exactly `+0`, so a program with no
    loop-backs renders pixel-identically to before this term existed.
    """
    if arm is None:
        return _BRANCH_SPACING
    # Measured in the arm's own frame, "forward" is the direction the arm
    # travels, so anything at negative forward-extent is content sitting
    # *behind* the subtree's entry point -- back toward the trunk.  Taking it
    # in the canonical frame avoids reasoning about rotated signs at all.
    min_forward, _, _, _ = _subtree_extent(arm)
    corridors = _count_gotos(arm) * _GOTO_CORRIDOR
    return _BRANCH_SPACING + max(-min_forward, 0) + corridors


def _layout(
    node: Node | None,
    cursor: _Cursor,
    entries: dict[int, tuple[tuple[int, int], tuple[int, int]]] | None = None,
    depth: int = 0,
    *,
    measuring: bool = False,
    pending: list[_Pending] | None = None,
) -> None:
    """Lay out ``node``'s chain from ``cursor``'s current point.

    ``entries`` maps a ``?`` node's ``id`` to ``(stem_start, heading)`` for
    the stem this function walks into that fork's own branch point -- a
    ``goto`` targeting it reconnects somewhere strictly *inside* that stem,
    not the branch point itself (see :func:`_close_loop` for why: the fork's
    own vertex, approached with the fork's own arrival heading, cannot be
    reached by any other straight line without retracing the stem itself).
    The exact offset along the stem is chosen lazily, by :func:`_close_loop`
    when :func:`_route_pending` routes the detour, rather than fixed here --
    a single pre-chosen offset (e.g. the stem's exact midpoint) can end up
    walled in by unrelated ink elsewhere in a dense decision tree happening to
    run directly alongside it (confirmed on a real boolean-generator brainfuck
    program's compiled output); trying several offsets sidesteps that.  Since
    detours are all routed after layout finishes (see :func:`_route_pending`),
    the occupancy those offsets are tested against is the finished drawing's,
    not a partial snapshot of whatever had been drawn so far.

    ``depth`` counts how many ``?`` forks deep this call is nested, and is
    carried purely for callers that want to know it -- arm spacing itself is
    sized by measured subtree extent (see :func:`_arm_spacing`), not by depth.

    ``measuring`` runs the layout purely to find out how much space a subtree
    occupies, for :func:`_subtree_extent`.  It makes a ``goto`` terminal
    instead of routing a real detour: routing needs the whole drawing's
    occupancy, which a subtree measured in isolation does not have, and the
    ``entries`` lookup a real ``goto`` performs would not find an ancestor
    fork that this subtree does not itself contain.  :func:`_route_pending`
    draws every detour after layout finishes instead.
    """
    if entries is None:
        entries = {}
    if pending is None:
        pending = []
    while node is not None:
        if node.op == "?":
            stem_start = (cursor.y, cursor.x)
            cursor.advance(cursor.heading, _STEM_LEN)
            entries[id(node)] = (stem_start, cursor.heading)
            right, left = cursor.branch()
            right.advance(right.heading, _arm_spacing(node.zero))
            right.finish()
            left.advance(left.heading, _arm_spacing(node.nonzero))
            left.finish()
            _layout(
                node.zero,
                right,
                entries,
                depth + 1,
                measuring=measuring,
                pending=pending,
            )
            _layout(
                node.nonzero,
                left,
                entries,
                depth + 1,
                measuring=measuring,
                pending=pending,
            )
            right.finish()
            left.finish()
            cursor.strokes.extend(right.strokes)
            cursor.strokes.extend(left.strokes)
            return
        op, count = node.op, 1
        if op in _MERGEABLE:
            while (
                node.next is not None and node.next.op == op and node.next.goto is None
            ):
                node = node.next
                count += 1
        cursor.emit_op(op, count)
        if node.goto is not None:
            # Flush the in-progress stroke's pixels into `occupied` before
            # going any further, so a detour later routed from here treats the
            # body just drawn (including this call's own final kink) as real
            # ink to route around.
            cursor.finish()
            if measuring:
                # A detour cannot be routed against a subtree's own isolated
                # occupancy, and this subtree need not even contain the fork
                # `goto` targets -- so measuring stops here.  Note this returns
                # *before* the `entries` lookup below, which would otherwise
                # KeyError on exactly that missing-ancestor case.
                return
            # Defer the actual routing to `render()`'s second phase rather than
            # routing it here, mid-layout -- see :func:`_route_pending`.
            pending.append(_Pending(cursor, node.goto, depth))
            return
        node = node.next
    cursor.finish()


def _arrowhead(
    draw: ImageDraw.ImageDraw, y: float, x: float, heading: tuple[int, int]
) -> None:
    """Draw the filled triangular cursor marker at (y, x), pointing ``heading``.

    Shape matches the arrowhead isolated from the wiki's reference images via
    distance-transform (a small filled triangle distinct from the 1px-wide
    path strokes), scaled to this renderer's ``_UNIT``.
    """
    hy, hx = heading
    ly, lx = _turn_left(heading)
    size = _UNIT * 0.35
    back = size * 0.6
    tip = (x + hx * size, y + hy * size)
    base_l = (x - hx * back + lx * back, y - hy * back + ly * back)
    base_r = (x - hx * back - lx * back, y - hy * back - ly * back)
    draw.polygon([tip, base_l, base_r], fill="black")


def render(root: Node, start_heading: tuple[int, int] = (-1, 0)) -> Image.Image:
    """Lay out and rasterize a Line program, returning a Pillow ``Image``.

    ``start_heading`` defaults to "up", matching every wiki example (the
    cursor starts at the bottom of the drawing and travels upward).
    """
    # See `_EXTENT_CACHE`: keyed by `id()`, so it must not outlive the nodes
    # it describes.  Clearing per render keeps every cached node reachable
    # from `root` for as long as its entry exists.
    _EXTENT_CACHE.clear()
    occupied: set[tuple[int, int]] = set()
    cursor = _Cursor(0, 0, start_heading, occupied=occupied)
    entries: dict[int, tuple[tuple[int, int], tuple[int, int]]] = {}
    pending: list[_Pending] = []
    _layout(root, cursor, entries, pending=pending)
    # Phase two: every loop-back detour routes here, against the finished
    # drawing rather than against however much of it happened to exist when
    # its own `goto` was reached -- see :func:`_route_pending`.
    cursor.strokes.extend(_route_pending(pending, entries, occupied))

    ys = [p[0] for stroke in cursor.strokes for p in stroke]
    xs = [p[1] for stroke in cursor.strokes for p in stroke]
    if not ys:
        raise ValueError("program produced an empty path")
    min_y, max_y = min(ys), max(ys)
    min_x, max_x = min(xs), max(xs)

    margin = _UNIT
    width = (max_x - min_x) * _UNIT + margin * 2
    height = (max_y - min_y) * _UNIT + margin * 2

    def to_px(pt: tuple[int, int]) -> tuple[float, float]:
        y, x = pt
        return (x - min_x) * _UNIT + margin, (y - min_y) * _UNIT + margin

    image = Image.new("L", (width, height), color=255)
    draw = ImageDraw.Draw(image)
    for stroke in cursor.strokes:
        draw.line([to_px(p) for p in stroke], fill=0, width=1)

    start_px, start_py = to_px((0, 0))
    _arrowhead(draw, start_py, start_px, start_heading)
    return image


if __name__ == "__main__":
    program = chain(*sys.argv[1]) if len(sys.argv) > 1 else chain("+", "+", "+")
    render(program).save(sys.argv[2] if len(sys.argv) > 2 else "line_out.png")
