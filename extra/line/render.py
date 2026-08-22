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
# Scope note, kept honest deliberately: the nested-loop regression this was
# written during turned out to be caused by a route touching *itself*, which
# `_self_approaches` is what actually fixes -- per-stroke attribution on
# `++[>++[>+<-]<-]>>.` showed all three arms of the spurious junction
# belonging to one single 530-cell detour.  Setting this to 0 currently
# leaves every test in `test_bf_to_line.py` and `test_line_boolean.py`
# passing, so no *checked-in* program is known to need between-stroke
# clearance today.  It is kept at 1 because the band probe's ±1 reach makes
# the abutting-ribbon failure real geometry rather than a hypothetical, and
# a route is free to run flush against unrelated ink without it -- but a
# future reader should know it is reasoned-from-the-probe, not
# pinned-by-a-failing-case, unlike everything else in this fix.
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

    def coarse_goal(p: tuple[int, int]) -> bool:
        return p in coarse_candidates

    def never_exempt(p: tuple[int, int]) -> bool:
        del p
        return False

    coarse_path = _astar(
        start,
        rounded,
        _UNIT,
        bounds,
        coarse_clear,
        is_goal=coarse_goal,
        exempt_goal=never_exempt,
    )
    if coarse_path is None:
        raise ValueError(
            "no clear route found for the loop-back detour within the "
            "current search padding -- the drawing may be too densely "
            "packed for this program's loop nesting"
        )
    coarse_target = coarse_path[-1]

    def fine_clear(p: tuple[int, int], direction: tuple[int, int]) -> bool:
        nxt = (p[0] + direction[0], p[1] + direction[1])
        return _clear_at(nxt, occupied, start)

    def fine_goal(p: tuple[int, int]) -> bool:
        return p == target

    def exempt_final(p: tuple[int, int]) -> bool:
        return p == target

    fine_path = _astar(
        coarse_target,
        target,
        1,
        bounds,
        fine_clear,
        is_goal=fine_goal,
        exempt_goal=exempt_final,
    )
    if fine_path is None:
        raise ValueError(
            "no clear route found for the loop-back detour's final approach "
            "within the current search padding -- the drawing may be too "
            "densely packed for this program's loop nesting"
        )

    return _path_to_legs(coarse_path + fine_path[1:])


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
                        (cursor.y, cursor.x), approach, occupied, padding
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


# Extra lateral distance (in grid units) each fork arm runs, purely as
# connective spacing, before `_layout` recurses into its actual content --
# scaled by remaining nesting depth (see `_layout`'s `depth` parameter and
# `_fork_depth` below) so sibling subtrees fan apart enough for whatever
# content they still need to lay out, without re-converging onto an
# ancestor fork's own arms.
#
# This *shrinks* geometrically the deeper a fork sits (an H-tree layout:
# each 90-degree turn needs roughly half its parent's arm length, not more),
# rather than growing with absolute nesting depth as an earlier version of
# this constant did.  Growing arms with depth seems intuitively safer (more
# room for deeper content) but is wrong: every fork turns its two children
# 90 degrees from its own heading, so a child fork's own children turn back
# toward the *original* heading -- if that grandchild's arm is longer than
# the distance back to its grandparent's axis, it overshoots and crosses
# it.  Confirmed concretely on a 3-level boolean-decision-tree generator
# (2**3 = 8 leaves): scaling this constant up by 10x reproduced the exact
# same "extraction left N source pixels unaccounted for" failure, because
# growing (not the absolute scale) was the bug -- every level's arm still
# overshot its ancestors' axes by the same ratio.  Halving per level instead
# (`_BRANCH_SPACING * 2 ** remaining_depth`, sized so the *shallowest*
# lookahead level still clears its own leaf content) keeps each inward turn
# strictly inside the space its ancestors left for it.
#
# Still needs to be large enough at the deepest level for `_close_loop` to
# route a BF-compiled loop-back through a densely nested decision tree
# (confirmed necessary on a real boolean-generator brainfuck program's
# compiled output) -- not a router bug, a genuine lack of drawn space
# between sibling branches for anything to route through otherwise.
_BRANCH_SPACING = 20


def _fork_depth(node: Node | None) -> int:
    """How many more nested `?` forks are reachable below ``node``.

    Walks `.next`/`.zero`/`.nonzero` (never `.goto`, which can cycle back to
    an ancestor -- see `Node.goto`'s docstring) to find the deepest `?`
    still ahead, so `_layout` can size a fork's own arm spacing against how
    much more branching that arm still has to fit, not just how deep the
    tree has already gone (see `_BRANCH_SPACING`'s comment for why depth
    from the root, growing outward, is the wrong quantity to scale on).
    """
    depth = 0
    while node is not None:
        if node.op == "?":
            return 1 + max(_fork_depth(node.zero), _fork_depth(node.nonzero))
        if node.goto is not None:
            return depth
        node = node.next
    return depth


def _layout(
    node: Node | None,
    cursor: _Cursor,
    entries: dict[int, tuple[tuple[int, int], tuple[int, int]]] | None = None,
    depth: int = 0,
) -> None:
    """Lay out ``node``'s chain from ``cursor``'s current point.

    ``entries`` maps a ``?`` node's ``id`` to ``(stem_start, heading)`` for
    the stem this function walks into that fork's own branch point -- a
    ``goto`` targeting it reconnects somewhere strictly *inside* that stem,
    not the branch point itself (see :func:`_close_loop` for why: the fork's
    own vertex, approached with the fork's own arrival heading, cannot be
    reached by any other straight line without retracing the stem itself).
    The exact offset along the stem is chosen lazily, by :func:`_close_loop`
    itself at the moment a ``goto`` actually fires, rather than fixed here --
    a single pre-chosen offset (e.g. the stem's exact midpoint) can end up
    walled in by unrelated ink drawn *after* this fork's own stem, e.g. a
    sibling branch elsewhere in a dense decision tree happening to run
    directly alongside it (confirmed on a real boolean-generator brainfuck
    program's compiled output); trying several offsets against the occupied
    set as it stands when the jump actually fires sidesteps that.

    ``depth`` counts how many ``?`` forks deep this call is nested, and
    grows :data:`_BRANCH_SPACING`'s effect the same way -- see its own
    comment for why deeper subtrees need more room, not just a fixed gap.
    """
    if entries is None:
        entries = {}
    while node is not None:
        if node.op == "?":
            stem_start = (cursor.y, cursor.x)
            cursor.advance(cursor.heading, _STEM_LEN)
            entries[id(node)] = (stem_start, cursor.heading)
            right, left = cursor.branch()
            remaining = 1 + max(_fork_depth(node.zero), _fork_depth(node.nonzero))
            spacing = _BRANCH_SPACING * 2**remaining
            right.advance(right.heading, spacing)
            right.finish()
            left.advance(left.heading, spacing)
            left.finish()
            _layout(node.zero, right, entries, depth + 1)
            _layout(node.nonzero, left, entries, depth + 1)
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
            stem_start, stem_heading = entries[id(node.goto)]
            # Flush the in-progress stroke's pixels into `occupied` *before*
            # routing, so the detour treats the body just drawn (including
            # this call's own final kink) as real ink to route around --
            # otherwise the router could path straight back through it.
            cursor.finish()
            assert cursor.occupied is not None
            _close_loop(cursor, stem_start, stem_heading, cursor.occupied)
            cursor.finish()
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
    cursor = _Cursor(0, 0, start_heading, occupied=set())
    _layout(root, cursor)

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
