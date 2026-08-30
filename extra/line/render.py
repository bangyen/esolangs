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

import itertools
import sys
from dataclasses import dataclass, field

import numpy as np
import png

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
    # cursor `branch()` creates from it, so `_layout`'s drift guard can
    # check a constructed loop-back against ink from sibling arms and the
    # trunk, not just its own cursor's strokes.  `None` (the default) means
    # occupancy tracking is off -- the case for `_subtree_extent`'s
    # measuring dry runs, whose construction is deterministic and needs no
    # guard.
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
    both), the layout draws a return path back to a point strictly inside
    the stem leading into whatever ``?`` node ``goto`` points at -- not the
    fork's own vertex (see :func:`_loop_return_legs` -- forcing the return
    to arrive with the fork's own arrival heading always retraces the
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

# How many *grid cells* of empty space a loop-back's path must keep between
# itself and any unrelated existing ink, beyond simply not overlapping it.
# One cell here is `_UNIT` raster pixels of real separation, since layout
# works entirely in cursor-grid space and `render` scales to pixels only
# when rasterizing.
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
# (Historically the *nested-loop regression itself* was a searched route
# touching *itself* -- per-stroke attribution on `++[>++[>+<-]<-]>>.` showed
# all three arms of the spurious junction belonging to one single 530-cell
# detour.  Constructed loop-backs cannot fold back on themselves, so only
# the between-stroke case remains live.)  This constant is pinned
# independently by `test_bf_to_line.py`'s `TestStrokeSeparation`: at 0,
# every program it checks develops between-stroke adjacency (up to 76
# consecutive abutting cells on `++[>++[>+<-]<-]>>+++.`), at 1 none does.
#
# That test exists because the ordinary suites do *not* catch this on their
# own -- they assert on program output, and a drawing can rasterize a 2px
# ribbon while still happening to extract and execute correctly.  Setting
# this to 0 left every other test passing, which is exactly why measuring
# stroke separation directly was needed to pin it.
_CLEARANCE = 1


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


# Length (in grid units) of the stem `_layout` walks into a `?` node's own
# branch point.  A loop-back lands strictly inside this run (at
# `_RETURN_STEM_T` from the vertex), so the stem must be long enough that
# the landing diagonal fits between its two real vertices.
_STEM_LEN = 10


# Length of a loop-back's final *diagonal* landing leg, in *grid cells* (so
# 6 here is 120 raster pixels, comfortably longer than `lattice.star`'s own
# 15px probe).
#
# The diagonal arrival is load-bearing, not cosmetic.  Every other leg of a
# return path is cardinal, and the stem being landed on is itself a cardinal
# run, so a cardinal final approach is necessarily *perpendicular* to the
# stem -- and a perpendicular touch-down onto a straight run lights exactly
# the arrival direction plus the stem's own two directions, which is
# precisely the T-branch signature `lattice._classify` calls a real
# `"fork"`.  The extractor would then read the loop-back merge as a
# conditional turn, and `simulate` would execute the reconnection as a
# branch instead of a jump.  Arriving diagonally lights that same stem pair
# plus a direction *not* perpendicular to it, which `_classify` correctly
# calls `"merge"` -- stopping the stroke as a leaf, exactly what
# `simulate._compile`'s `find_merge` rescues into a `goto`.  This matches
# how the wiki's own hand-drawn fixtures reconnect (`addition.png`'s
# loop-body arm arrives at its stem on a diagonal).
#
# Being *longer* than the probe is what makes this work, not shorter: the
# probe must find a full, unbroken band segment along the diagonal so the
# merge point lights that third direction and `lattice._classify` reads
# `"merge"`.  A diagonal too short to fill the probe would leave the merge
# point reading only the stem's own two directions -- an ordinary
# `"straight"` bend, which the walker would sail straight through, continuing
# down the stem instead of stopping the stroke as a leaf.
_DIAGONAL_APPROACH = 6


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


# Width, in grid cells, of the corridor one loop-back's path needs to pass
# an arm -- see :func:`_arm_spacing`, which reserves one of these on any
# `goto`-carrying arm, and whose floor-plus-corridor sum is what guarantees
# :func:`_loop_return_legs` a bay at least ``_BRANCH_SPACING +
# _GOTO_CORRIDOR`` = 8 cells wide between body content and the trunk axis.
#
# This is not a chosen number, which matters: a fixed `_GOTO_CHANNEL`
# constant was tried during the depth-3 work and removed precisely because
# it was guessing at a quantity nothing had measured.  It is the swath a
# drawn path actually blocks: one cell of its own stroke, plus `_CLEARANCE`
# of mandated gap on either side.  Written as the expression rather than its
# value so that changing `_CLEARANCE` moves the corridors with it.
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


def _has_goto(node: Node | None, seen: set[int] | None = None) -> bool:
    """Whether ``node``'s subtree contains a loop-back needing a bay corridor.

    Walks the same `.next`/`.zero`/`.nonzero` edges :func:`_subtree_extent`
    does, and stops at a `goto` rather than following it (it cycles back to
    an ancestor -- see :class:`Node`'s docstring).  A boolean, not a count:
    :func:`_arm_spacing` reserves one corridor for any goto-carrying arm
    regardless of how many loop-backs nest beneath it (a per-goto multiplier
    was measured off -- see its docstring).
    """
    if seen is None:
        seen = set()
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        if node.goto is not None:
            return True
        if node.op == "?":
            return _has_goto(node.zero, seen) or _has_goto(node.nonzero, seen)
        node = node.next
    return False


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
    the heavier one is exactly the case that exhausted the since-removed
    search-based router under fork-count spacing.
    A fork's two arms are sized identically for the same reason, even when
    wildly asymmetric (the depth-0 fork above has 4 ops on one arm and 14 on
    the other).  Extent is the quantity the layout actually needs, so it is
    now the quantity measured.

    Deliberately runs the *real* :func:`_layout` against a scratch cursor
    rather than reimplementing its geometry: a parallel size-estimating walk
    would drift from the code that actually draws, and then every extent it
    reports is a quiet lie.  The dry run draws every *nested* loop-back
    (their target forks live inside the measured chain, so their constructed
    returns are pure local geometry -- see :func:`_loop_return_legs`), which
    is exactly what lets ancestors reserve room for them; only the chain's
    own outermost ``goto`` is treated as terminal, since its target fork
    belongs to the caller's frame, and that is precisely where its return
    path gets drawn instead.
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

    On top of that, a ``goto``-carrying arm reserves one
    :data:`_GOTO_CORRIDOR`.  This is what *guarantees*
    :func:`_loop_return_legs` its bay: such an arm's run is at least
    ``_BRANCH_SPACING + _GOTO_CORRIDOR`` = 8 longer than its content reaches
    back, so the gap between body content and the trunk axis always fits the
    bay lane at lateral offset :data:`_DIAGONAL_APPROACH` with `_CLEARANCE`
    to spare on both sides -- and 8 is exactly that sum, so the corridor is
    the minimum, not a margin.

    One corridor, not one per ``goto`` beneath the arm.  The per-goto
    multiplier dated from the search-routing era, when `n` free-form detours
    could all cross one gap and each blocked a corridor of it; constructed
    returns never share a gap that way -- every nested loop-back rides its
    *own* fork's bay, and parents reserve room for it through the measured
    extent, not through this term.  Measured on the depth ladder when the
    multiplier was dropped: every program still round-trips, flat-loop
    drawings are pixel-identical, and nested areas shrink 17% at depth 4 to
    44% at depth 10 (the multiplier compounded through nested extents, so
    its cost grew with depth just as its removal's savings do).

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
    corridors = _GOTO_CORRIDOR if _has_goto(arm) else 0
    return _BRANCH_SPACING + max(-min_forward, 0) + corridors


# Offset, in grid cells, at which a constructed loop-back ring runs outside
# its body's bounding box.  2 is the smallest offset whose cells satisfy
# `_CLEARANCE` = 1 against ink sitting exactly on the box edge (the cell
# between is empty).
_RING_OFFSET = _CLEARANCE + 1

# The fixed stem offset a constructed loop-back lands on, from the fork
# vertex (so `_STEM_LEN - _RETURN_STEM_T` cells past `stem_start`).  Any
# interior offset works -- the construction reserves its whole landing
# geometry, so unlike the removed router's offset scan nothing can wall one
# choice in -- and the midpoint keeps the diagonal clear of both stem ends.
_RETURN_STEM_T = _STEM_LEN // 2


def _loop_return_legs(
    start: tuple[int, int],
    target: Node,
    entries: dict[int, tuple[tuple[int, int], tuple[int, int]]],
) -> list[tuple[tuple[int, int], int]] | None:
    """Construct a loop-back's legs deterministically, without search.

    This is what makes nesting depth unbounded.  Search-based routing
    competes for space globally, so every added depth was a new congestion
    problem (see ``WIP.md``'s depth-4/5 entries); this constructs the return
    path from measured geometry alone, and because both the real layout
    *and* :func:`_subtree_extent`'s dry runs draw it (see :func:`_layout`'s
    ``goto`` branch), every parent's measured extent already contains its
    children's return paths -- the same recursion that makes parents reserve
    room for child *content* reserves room for child *rings*, at every
    depth, with nothing left to collide.

    The shape, in the target fork's own frame (``+y`` = the body arm's
    heading, origin at the arm entry -- everything is built here as integer
    legs and rotated onto the world at the end):

    - ``B0``, the body's bounding box, is the memoized
      :func:`_subtree_extent` of the fork's ``nonzero`` arm: all body ink
      including nested loops' own return paths, excluding this return path.
    - From the body's end (which sits on ``B0``'s perimeter -- measured true
      at every depth tried, and checked below), step :data:`_RING_OFFSET`
      outward, then walk the ring around ``B0`` to the corner nearest the
      stem, always arriving on the bay side via that corner so the path
      never crosses the arm stroke (which pierces the bay line at
      ``x = 0``).
    - Ride the bay -- the gap :func:`_arm_spacing` reserves between body
      content and the trunk axis, at least ``_BRANCH_SPACING +
      _GOTO_CORRIDOR`` = 8 wide for any goto-carrying arm -- to the landing
      approach, and close with a :data:`_DIAGONAL_APPROACH` diagonal (the
      diagonal arrival is what makes the extractor read a ``"merge"`` rather
      than a spurious fork -- see that constant's comment).

    Returns world-frame ``(direction, length)`` legs, or ``None`` when a
    premise fails (body end off the perimeter, degenerate geometry) -- a
    shape only a hand-built graph can produce, which :func:`_layout` then
    rejects loudly rather than misdrawing.
    """
    stem_start, h = entries[id(target)]
    a_h = _turn_left(h)
    arm_run = _arm_spacing(target.nonzero)
    vertex = (
        stem_start[0] + h[0] * _STEM_LEN,
        stem_start[1] + h[1] * _STEM_LEN,
    )
    entry_pt = (vertex[0] + a_h[0] * arm_run, vertex[1] + a_h[1] * arm_run)
    y0, y1, x0, x1 = _subtree_extent(target.nonzero)

    # `start` in the canonical frame: project the world offset onto the
    # frame's axes (+y = a_h, +x = turn_left(a_h); the rotation is
    # orthonormal, so projection inverts `_rotate` exactly).
    ly, lx = _turn_left(a_h)
    off = (start[0] - entry_pt[0], start[1] - entry_pt[1])
    ey = off[0] * a_h[0] + off[1] * a_h[1]
    ex = off[0] * ly + off[1] * lx
    on_y = ey in (y0, y1) and x0 <= ex <= x1
    on_x = ex in (x0, x1) and y0 <= ey <= y1
    if not (on_y or on_x):
        return None

    axis_y = -arm_run
    bay_y = y0 - _RING_OFFSET
    far_y = y1 + _RING_OFFSET
    lo_x = x0 - _RING_OFFSET
    hi_x = x1 + _RING_OFFSET
    # The bay must clear both the trunk axis and the diagonal's own lateral
    # span; `_arm_spacing`'s floor + corridor guarantees this for any
    # goto-carrying arm, so a failure here means a hand-built graph whose
    # arm the corridor term never saw.
    if bay_y < axis_y + _DIAGONAL_APPROACH:
        return None

    tgt_x = _STEM_LEN - _RETURN_STEM_T
    approach = (axis_y + _DIAGONAL_APPROACH, tgt_x + _DIAGONAL_APPROACH)

    # Waypoints around the ring, always entering the bay line via the
    # rear corner `(bay_y, hi_x)` so the bay is never traversed across the
    # arm stroke at x = 0 (every bay segment used lies at x >= 1).
    pts: list[tuple[int, int]] = [(ey, ex)]
    if on_x and ex == x1:  # rear side: out, then down to the bay corner
        pts += [(ey, hi_x), (bay_y, hi_x)]
    elif on_y and ey == y1:  # far side: out, over the far-rear corner, down
        pts += [(far_y, ex), (far_y, hi_x), (bay_y, hi_x)]
    elif on_x and ex == x0:  # vertex-ward side: the long way around
        pts += [(ey, lo_x), (far_y, lo_x), (far_y, hi_x), (bay_y, hi_x)]
    else:  # bay side
        if ex == 0:
            # The escape would land exactly on the arm stroke's own line.
            return None
        if ex >= 1:
            pts += [(bay_y, ex)]
        else:
            # Left of the arm stroke: the direct bay run would cross it, so
            # take the long way around the ring.
            pts += [(bay_y, ex), (bay_y, lo_x), (far_y, lo_x), (far_y, hi_x)]
            pts += [(bay_y, hi_x)]
    pts += [(bay_y, approach[1]), approach]

    legs: list[tuple[tuple[int, int], int]] = []
    for a, b in itertools.pairwise(pts):
        dy, dx = b[0] - a[0], b[1] - a[1]
        if dy and dx:  # pragma: no cover - geometry guard
            return None
        if not dy and not dx:
            continue
        direction = (
            0 if dy == 0 else (1 if dy > 0 else -1),
            0 if dx == 0 else (1 if dx > 0 else -1),
        )
        legs.append((direction, abs(dy) + abs(dx)))
    legs.append(((-1, -1), _DIAGONAL_APPROACH))

    return [(_rotate(d, a_h), n) for d, n in legs]


def _layout(
    node: Node | None,
    cursor: _Cursor,
    entries: dict[int, tuple[tuple[int, int], tuple[int, int]]] | None = None,
    depth: int = 0,
    *,
    measuring: bool = False,
) -> None:
    """Lay out ``node``'s chain from ``cursor``'s current point.

    ``entries`` maps a ``?`` node's ``id`` to ``(stem_start, heading)`` for
    the stem this function walks into that fork's own branch point -- a
    ``goto`` targeting it reconnects somewhere strictly *inside* that stem
    (at :data:`_RETURN_STEM_T` from the vertex), not the branch point
    itself: the fork's own vertex, approached with the fork's own arrival
    heading, cannot be reached by any other straight line without retracing
    the stem itself.  :func:`_loop_return_legs` is what draws the
    reconnection, at the moment the ``goto`` is reached.

    ``depth`` counts how many ``?`` forks deep this call is nested, and is
    carried purely for callers that want to know it -- arm spacing itself is
    sized by measured subtree extent (see :func:`_arm_spacing`), not by depth.

    ``measuring`` runs the layout purely to find out how much space a subtree
    occupies, for :func:`_subtree_extent`.  The one asymmetry with the real
    pass is a ``goto`` whose target fork is outside the measured chain (the
    chain's own outermost loop-back): its return path is drawn by whichever
    frame *does* contain the fork, so measuring treats it as terminal.
    Every nested ``goto``'s return path is drawn in both modes, which is
    what makes ancestors reserve room for them (see
    :func:`_loop_return_legs`).
    """
    if entries is None:
        entries = {}
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
            _layout(node.zero, right, entries, depth + 1, measuring=measuring)
            _layout(node.nonzero, left, entries, depth + 1, measuring=measuring)
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
            # going any further, so whatever draws the loop-back from here
            # treats the body just drawn (including this call's own final
            # kink) as real ink.
            cursor.finish()
            # The constructed return path -- see :func:`_loop_return_legs`.
            # Drawn *here*, in both real and measuring mode, is what makes
            # nesting unbounded: a dry run that draws its subtree's returns
            # reports extents that contain them, so every ancestor reserves
            # room for them exactly as it does for content.  The target must
            # already be in `entries` (always true for a compiled brainfuck
            # graph, where a goto ends its own fork's body chain; a subtree
            # measured in isolation lacks its own outermost fork, which is
            # precisely the ink the *caller's* frame draws instead).
            legs = None
            if id(node.goto) in entries:
                legs = _loop_return_legs((cursor.y, cursor.x), node.goto, entries)
            if legs is not None and cursor.occupied is not None:
                # Drift guard, real mode only: the construction never
                # consults ink, so a violated premise (a hand-built graph
                # outside the compiled invariants) must be caught rather
                # than drawn through existing strokes.  Overlap-only -- the
                # first cell is the body's own tip and the last is the stem
                # merge, both legitimately ink.
                cells = _leg_cells((cursor.y, cursor.x), legs)
                if any(c in cursor.occupied for c in cells[1:-1]):
                    legs = None
            if legs is not None:
                for direction, length in legs:
                    cursor.advance(direction, length)
                cursor.finish()
                return
            if measuring:
                # No constructed return (the goto's target is outside this
                # measured subtree): stop here, exactly as the pre-return
                # semantics of extents require -- the owner's frame draws it.
                return
            # A goto whose return path cannot be constructed only exists in
            # a hand-built graph outside the compiled invariants (target not
            # an ancestor fork whose body chain the goto ends, or a body end
            # off its own box perimeter).  Failing loudly here is the
            # invariant that survives from the removed search-based router:
            # never draw a reconnection through existing ink and let the
            # extractor misread it.
            raise ValueError(
                "loop-back could not be constructed for this goto -- its "
                "target must be an ancestor '?' fork whose body chain the "
                "goto ends (the shape bf_to_line compiles); see "
                "_loop_return_legs for the geometric premises"
            )
        node = node.next
    cursor.finish()


class Canvas:
    """An 8-bit greyscale raster with the two drawing primitives Line needs.

    Line drawings are 1px strokes plus one small filled triangle, so this is
    Bresenham and a scanline fill over a numpy array rather than anything
    general.  What matters is not matching a particular graphics library
    pixel-for-pixel but that :mod:`extract` can read the result back: strokes
    stay exactly 1px wide (:func:`extract.detect_scale` infers the drawing's
    scale from that), and the arrowhead stays the only region thick enough to
    survive an erosion, with a fill ratio inside
    :data:`extract._FILL_RATIO_RANGE`.
    """

    def __init__(self, width: int, height: int, colour: int = 255) -> None:
        """Create a ``width`` x ``height`` canvas filled with ``colour``."""
        self.pixels = np.full((height, width), colour, dtype=np.uint8)

    def line(self, points: list[tuple[float, float]], colour: int = 0) -> None:
        """Stroke a 1px-wide polyline through ``points`` given as ``(x, y)``."""
        for (x0, y0), (x1, y1) in itertools.pairwise(points):
            self._segment(round(x0), round(y0), round(x1), round(y1), colour)

    def _segment(self, x0: int, y0: int, x1: int, y1: int, colour: int) -> None:
        """Bresenham's line algorithm, plotting one pixel per step."""
        height, width = self.pixels.shape
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        step_x = 1 if x0 < x1 else -1
        step_y = 1 if y0 < y1 else -1
        error = dx + dy
        while True:
            if 0 <= y0 < height and 0 <= x0 < width:
                self.pixels[y0, x0] = colour
            if x0 == x1 and y0 == y1:
                return
            doubled = 2 * error
            if doubled >= dy:
                error += dy
                x0 += step_x
            if doubled <= dx:
                error += dx
                y0 += step_y

    def polygon(self, points: list[tuple[float, float]], colour: int = 0) -> None:
        """Fill the polygon through ``points`` given as ``(x, y)``.

        A scanline fill: for each row crossing the shape, find where its edges
        cross that row's centre and paint between consecutive crossings.  The
        outline is stroked too, so a triangle thinner than a pixel in places
        still comes out connected rather than dotted.
        """
        height, width = self.pixels.shape
        ys = [y for _, y in points]
        for row in range(max(0, int(min(ys))), min(height, int(max(ys)) + 2)):
            centre = row + 0.5
            crossings = []
            for (x0, y0), (x1, y1) in itertools.pairwise([*points, points[0]]):
                if (y0 > centre) != (y1 > centre):
                    crossings.append(x0 + (centre - y0) / (y1 - y0) * (x1 - x0))
            crossings.sort()
            for left, right in zip(crossings[::2], crossings[1::2], strict=False):
                start = max(0, round(left))
                stop = min(width, round(right) + 1)
                self.pixels[row, start:stop] = colour
        self.line([*points, points[0]], colour)

    def save(self, path: str) -> None:
        """Write the canvas to ``path`` as an 8-bit greyscale PNG."""
        png.write_grey_file(path, self.pixels)


def _arrowhead(draw: Canvas, y: float, x: float, heading: tuple[int, int]) -> None:
    """Draw the filled triangular cursor marker at (y, x), pointing ``heading``.

    Shape matches the arrowhead isolated from the wiki's reference images (a
    small filled triangle distinct from the 1px-wide path strokes), scaled to
    this renderer's ``_UNIT``.
    """
    hy, hx = heading
    ly, lx = _turn_left(heading)
    size = _UNIT * 0.35
    back = size * 0.6
    tip = (x + hx * size, y + hy * size)
    base_l = (x - hx * back + lx * back, y - hy * back + ly * back)
    base_r = (x - hx * back - lx * back, y - hy * back - ly * back)
    draw.polygon([tip, base_l, base_r], colour=0)


def render(root: Node, start_heading: tuple[int, int] = (-1, 0)) -> Canvas:
    """Lay out and rasterize a Line program, returning a :class:`Canvas`.

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
    _layout(root, cursor, entries)

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

    canvas = Canvas(width, height)
    for stroke in cursor.strokes:
        canvas.line([to_px(p) for p in stroke])

    start_px, start_py = to_px((0, 0))
    _arrowhead(canvas, start_py, start_px, start_heading)
    return canvas


if __name__ == "__main__":
    program = chain(*sys.argv[1]) if len(sys.argv) > 1 else chain("+", "+", "+")
    render(program).save(sys.argv[2] if len(sys.argv) > 2 else "line_out.png")
