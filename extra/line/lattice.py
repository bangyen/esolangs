"""Extract a Line program's path tree by probing 8-pointed stars at each vertex.

Alternative to :mod:`extract`'s greedy pixel-by-pixel walker plus region-
adjacency junction detection.  That walker's one known structural gap (see
``WIP.md``) is a merge: the wiki's own drawings let one stroke's last leg
run straight into a *different*, already-drawn stroke's ink with no
separating background pixel, which a pixel-adjacency walk cannot tell apart
from an ordinary continuation -- three attempts at a local pixel-geometry
fix each broke on some new bend not covered by the fixture used to derive
it.

This module instead asks, at every vertex, a single question: probe all 8
compass directions for a real line segment leaving that point, and count how
many are lit.

* 2 lit directions (the one arrived from, plus one more): an ordinary bend
  -- continue the stroke through it.
* 3 lit directions: either a real conditional-turn fork or an incidental
  merge with an unrelated stroke -- both stop the current stroke here (see
  below for how the two are told apart).
* 4 lit directions: a crossing -- two unrelated strokes overlapping, with
  the cursor passing straight through untouched.

Merge detection falls out of this almost for free: a merge point, hand-
decoded in ``WIP.md`` for ``fixtures/multiplication.png``'s confirmed
``(194, 228)`` junction, has exactly 3 lit directions at the exact pixel the
merging stroke touches the unrelated one it runs into, the same reading a
real conditional-turn's stem tip has -- so the walker naturally stops there,
rather than needing a dedicated signal to detect the merge as a special
case.  What still separates a real fork from an incidental merge is the
same geometric fact :func:`extract._walk_tree` already uses: a real
conditional turn's *other* two lit directions (besides the one arrived
from) are the pair perpendicular to the arrival heading, matching the
wiki's T-branch shape (see ``render.py``'s ``_Cursor.branch``) -- an
incidental merge's extra direction essentially never lands exactly there.

The probe itself checks a 3-pixel-wide band (the exact ray, plus one pixel
to each side, perpendicular to that ray's own direction), not a single
1px-wide ray.  A single-ray probe was tried first and broke twice on real
fixtures: hand-drawn curves don't sit at one exact pixel width, so an exact-
length single ray can miss a real segment that is a pixel short of the
nominal grid unit, and a walked path's own recorded stopping pixel can be
one row/column off the true geometric vertex (confirmed on
``fixtures/addition.png``'s real T-junction, whose bar sits one row above
where the incoming stem's own path data ends).  The band absorbs both: the
true segment shows up on one of its three parallel rays even when the probe
is anchored a pixel off-center, and its *length* is read directly off where
all three rays lose ink at once, rather than needing a separately guessed or
tolerance-padded unit length.  Verified against every direction-change
vertex in both wiki reference fixtures (~90 total): every ordinary bend
reads exactly 2, every real fork or merge point reads exactly 3 (including
the confirmed ``(194, 228)`` merge and the real T-junctions in both
fixtures), and the only other reading (1) is a genuine stroke dead end.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# 8 directions in (dy, dx) form, indexed 0..7 as N, NE, E, SE, S, SW, W, NW --
# the same indexing render.py's headings would map onto, so a direction index
# here and a (dy, dx) heading there describe the same geometry.  Owned by
# this module (rather than extract.py, which also uses it) since extract.py
# already depends on this module's walker -- extract.py imports it back from
# here instead of the two modules importing from each other.
_DIRS: list[tuple[int, int]] = [
    (-1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
    (1, 0),
    (1, -1),
    (0, -1),
    (-1, -1),
]


def _ink(mask: np.ndarray, y: int, x: int) -> bool:
    h, w = mask.shape
    return 0 <= y < h and 0 <= x < w and bool(mask[y, x])


# Matches render.py's _UNIT: the nominal grid spacing (in source pixels)
# between corners in a Line drawing.  Only used as an upper bound on how far
# a single segment is walked before giving up -- see _walk_segment -- since
# the band probe (see module docstring) already reads a segment's actual
# length directly rather than assuming this exactly, and real fixtures
# measure a pixel or two off it in practice.
UNIT = 20

# Upper bound on how long a single walked segment is allowed to be before
# _walk_segment gives up rather than looping indefinitely on a corrupted or
# unexpected image.  Not a small multiple of UNIT: a merged run of several
# consecutive `+`/`-` opcodes draws as a single, proportionally longer
# straight/diagonal run with no intermediate corner at all (see
# render.py's module docstring), and fixtures/multiplication.png's own
# longest run measures ~60px (three units) with no wiki-documented ceiling
# on the repeat count -- so this is generous headroom above what either
# fixture needs, not a tight bound.
_MAX_SEGMENT = UNIT * 20


def _band_lit(mask: np.ndarray, y: int, x: int, direction: int) -> bool:
    """Whether any of the 3 parallel rays (center + 1px either side) is ink.

    The 3 rays run parallel to ``direction`` but are offset from ``(y, x)``
    along the *perpendicular* axis -- see module docstring for why a single
    center ray is not enough (a real segment can be a pixel off the exact
    probe center, at a hand-drawn corner's true vertex).
    """
    dy, dx = _DIRS[direction]
    pdy, pdx = _DIRS[(direction + 2) % 8]
    return any(_ink(mask, y + pdy * k, x + pdx * k) for k in (-1, 0, 1))


def star(mask: np.ndarray, y: int, x: int, length: int = 15) -> set[int]:
    """Which of the 8 directions have a real band segment from this vertex.

    ``length`` only needs to be shorter than the shortest real segment
    anywhere in the drawing (see module docstring's band-probe rationale --
    the exact length is not load-bearing the way it was in an earlier,
    discarded exact-match design); the default comfortably clears every
    real segment length measured on both wiki fixtures (all >= 19px)
    without risking running past a short real segment into whatever
    happens to follow it.
    """
    lit = set()
    for idx, (dy, dx) in enumerate(_DIRS):
        if all(
            _band_lit(mask, y + dy * i, x + dx * i, idx) for i in range(1, length + 1)
        ):
            lit.add(idx)
    return lit


# How many pixels of real, unbroken ink _snap requires before trusting a
# perpendicular-offset candidate as the true centerline for a chosen
# direction -- long enough to tell a genuine leg (segments on both wiki
# fixtures all measure >= 19px, see star's own default) apart from a
# neighboring, unrelated leg's ink brushing past for a pixel or two (e.g.
# a diagonal leg's own body passing near a perpendicular bar one row over,
# confirmed to falsely satisfy a 1-pixel-deep check at fixtures/addition.png's
# V-notch corner).
_SNAP_CONFIRM = 6


def _snap(mask: np.ndarray, y: int, x: int, direction: int) -> tuple[int, int]:
    """Find which of ``(y, x)``'s band offsets is the true centerline for ``direction``.

    A vertex's own recorded position can be a pixel off the true corner of
    the leg leaving in ``direction`` -- confirmed on both fixtures, e.g. a
    diagonal leg touching down one row below the horizontal bar it turns
    into, rather than exactly on the bar's own row (the same geometry
    :func:`_classify`'s band-tolerant :func:`star` already looks past to
    classify the vertex correctly).  :func:`_walk_segment` cannot use that
    same leniency for every step without risking the overshoot-onto-foreign-
    ink problem the band was built to avoid, so instead this snaps *once*,
    right before walking a specific chosen direction: of ``(y, x)`` and its
    two perpendicular-offset neighbors, return whichever one has a real,
    several-pixel-deep run in ``direction`` -- the true centerline for that
    specific leg, whatever pixel the previous leg's own walk happened to
    land on.  Requiring several pixels, not just one, is load-bearing: a
    single step is not enough to tell a genuine leg apart from a
    *different*, nearby leg's own ink brushing past for a pixel (confirmed
    to happen one row off the true corner in exactly this situation).
    """
    dy, dx = _DIRS[direction]
    pdy, pdx = _DIRS[(direction + 2) % 8]
    for k in (0, 1, -1):
        cy, cx = y + pdy * k, x + pdx * k
        if all(
            _ink(mask, cy + dy * i, cx + dx * i) for i in range(1, _SNAP_CONFIRM + 1)
        ):
            return cy, cx
    return y, x


def _walk_segment(mask: np.ndarray, y: int, x: int, direction: int) -> tuple[int, int]:
    """Follow a stroke's own center pixels to this segment's true endpoint.

    Advances pixel by pixel while the exact next pixel (not the wider band
    -- see below) is ink, and returns the last position where it was.  The
    band probe (:func:`_band_lit`, :func:`star`) is deliberately *not* used
    for this per-step advance: it is lenient by design (any of 3 parallel
    rays counts), which is exactly right for asking "is there a segment
    roughly this way" from a possibly slightly-off-center vertex, but wrong
    for walking forward along a stroke's own centerline -- confirmed to
    overshoot the true endpoint by a pixel in practice, continuing onto a
    *different* leg's ink that happens to sit within the band's lateral
    reach of the true corner rather than stopping there.
    """
    dy, dx = _DIRS[direction]
    py, px = y, x
    for _ in range(_MAX_SEGMENT):
        ny, nx = py + dy, px + dx
        if not _ink(mask, ny, nx):
            return py, px
        py, px = ny, nx
    return py, px


def find_start(
    mask: np.ndarray, approx_y: int, approx_x: int, heading: int
) -> tuple[int, int]:
    """Return the path-start vertex for a caller already holding one.

    :func:`extract.find_cursor`'s centroid-derived nearest-ink-pixel search
    (the same search :func:`extract.extract_tree` already does) lands
    directly on the arrowhead's own true tip in practice -- confirmed on
    both fixtures, where the located pixel sits exactly at one end of the
    first opcode's own straight run, with nothing between it and the blob
    boundary.  This function is a thin passthrough, kept as the one named
    entry point a caller plugs that search's result into (mirroring
    :func:`extract.extract_tree`'s own start-pixel step); ``mask``/
    ``heading`` are accepted for interface symmetry with the rest of the
    module's direction- and mask-aware functions rather than being used.
    """
    del mask, heading
    return approx_y, approx_x


@dataclass
class Vertex:
    """One lattice point the walk passes through, plus the heading taken.

    ``heading`` is the direction (a :data:`extract._DIRS` index) travelled
    *away* from this vertex toward the next one -- ``None`` for a stroke's
    final vertex, which has no further direction.
    """

    y: int
    x: int
    heading: int | None


@dataclass
class Stroke:
    """One matched straight-through run of lattice vertices, tree-shaped.

    Mirrors :class:`extract.Stroke`'s shape (``zero``/``nonzero`` branches),
    but the path is a list of on-lattice :class:`Vertex` objects rather than
    a dense pixel-by-pixel path -- the walk only ever visits real vertices,
    not the pixels between them.
    """

    vertices: list[Vertex]
    zero: Stroke | None = None
    nonzero: Stroke | None = None

    @property
    def end(self) -> tuple[int, int]:
        v = self.vertices[-1]
        return v.y, v.x


def _opposite(idx: int) -> int:
    return (idx + 4) % 8


def _classify(lit: set[int], back: int) -> tuple[str, list[int]]:
    """Decide what kind of vertex this is, given its lit directions.

    ``lit`` is this vertex's full :func:`star` result, including ``back``
    (the direction already walked in from).  Returns a ``(kind, options)``
    pair:

    * ``"end"``: ``lit`` is just ``{back}`` -- a genuine dead end, nothing
      more to walk.
    * ``"straight"``: exactly one direction besides ``back`` is lit --
      an ordinary bend; continue the stroke through it.
    * ``"crossing"``: exactly 4 directions lit, including ``back`` and the
      direction straight ahead (opposite ``back``) -- two unrelated strokes
      overlapping; matches :func:`extract._walk_tree`'s own crossing rule
      (see its docstring) by passing straight through rather than treating
      it as a decision point.
    * ``"fork"``: exactly 3 directions lit, and the two besides ``back``
      are the pair perpendicular to it (``back +/- 2``) -- a real
      conditional turn, matching the wiki's T-branch shape.  ``options``
      has those two directions, right (zero) first.
    * ``"merge"``: exactly 3 directions lit, but the extra two aren't the
      perpendicular pair -- an incidental merge into an unrelated stroke
      (see module docstring), not a real decision point.  Stops the
      current stroke the same way ``"end"`` does, just for a different
      reason (kept as a separate kind purely so a caller can tell the two
      apart if useful, e.g. for diagnostics).
    """
    rest = lit - {back}
    if not rest:
        return "end", []
    if len(rest) == 1:
        return "straight", list(rest)
    right, left = (back + 2) % 8, (back - 2) % 8
    straight = _opposite(back)
    if len(lit) == 4 and back in lit and straight in lit:
        return "crossing", [straight]
    if len(rest) == 2 and right in rest and left in rest:
        return "fork", [right, left]
    return "merge", []


def _resnap_dead_end(mask: np.ndarray, y: int, x: int, heading: int) -> tuple[int, int]:
    """Recover a vertex :func:`_walk_segment` stopped a column short of.

    ``_walk_segment`` advances in exactly one direction, so if the true
    corner it is walking toward sits one pixel over on the perpendicular
    axis (the same off-by-one geometry :func:`_snap` corrects for when
    *continuing* a stroke -- see its docstring), the segment can run out of
    ink one step early and land on a pixel whose only lit direction is
    ``back`` -- reading as a genuine dead end when a real bend sits right
    next to it.  Confirmed on ``fixtures/multiplication.png``: a walked S
    segment stops at ``(72, 267)`` (``star`` reads only ``{N}`` there) one
    column short of the true NE-turning corner at ``(72, 268)`` (``star``
    reads ``{N, NE}``), silently truncating an entire ~460px downstream
    branch with no error -- caught by comparing this walker's coverage
    against :mod:`extract`'s pixel-adjacency walker on the same fixture.

    Only called when ``star`` at ``(y, x)`` itself already looks like a
    dead end (see :func:`walk_tree`) -- a vertex that classifies as
    anything else is trusted as-is, so this cannot turn a real fork or
    merge into something else.  Tries both perpendicular-to-``heading``
    neighbors (mirroring the ``k in (-1, 1)`` offsets :func:`_snap` already
    uses) and returns the first whose own ``star`` reads as more than just
    ``back`` -- i.e. a real bend was found one pixel over; returns
    ``(y, x)`` unchanged if neither does, which is what a genuine dead end
    looks like.
    """
    back = _opposite(heading)
    pdy, pdx = _DIRS[(heading + 2) % 8]
    for k in (-1, 1):
        cy, cx = y + pdy * k, x + pdx * k
        if star(mask, cy, cx) - {back}:
            return cy, cx
    return y, x


def walk_tree(
    mask: np.ndarray,
    start: tuple[int, int],
    heading: int,
    visited: set[tuple[int, int]] | None = None,
) -> Stroke:
    """Walk a Line image's full path tree via star-probing from ``start``.

    ``start``/``heading`` must be a real vertex and the direction leaving it
    (see :func:`find_start` for the initial call).  At each vertex, probes
    all 8 directions (:func:`star`) and follows :func:`_classify`'s verdict:
    continues through ``"straight"``/``"crossing"`` points, stops the
    stroke at ``"end"``/``"merge"``, and recurses into both arms at a
    ``"fork"`` -- matching :func:`extract._walk_tree`'s own branch
    recursion, but deciding each step from one star probe instead of a
    pixel-by-pixel walk plus region-adjacency junction detection.

    ``visited`` tracks vertices already claimed by this call tree, the same
    role :func:`extract._walk`'s ``visited`` set plays -- needed so a branch
    arm can never wander back onto a vertex an earlier arm already walked
    through (confirmed necessary: two arms of the same fork can legitimately
    both approach the same far-away vertex from different directions on a
    looping program).
    """
    if visited is None:
        visited = set()
    y, x = start
    vertices: list[Vertex] = []
    visited.add((y, x))

    while True:
        vertices.append(Vertex(y, x, heading))
        y, x = _walk_segment(mask, y, x, heading)

        if (y, x) in visited:
            vertices.append(Vertex(y, x, None))
            return Stroke(vertices)

        back = _opposite(heading)
        lit = star(mask, y, x)
        if not lit - {back}:
            y, x = _resnap_dead_end(mask, y, x, heading)
            lit = star(mask, y, x)
        visited.add((y, x))
        kind, options = _classify(lit, back)

        if kind == "fork":
            vertices.append(Vertex(y, x, None))
            stroke = Stroke(vertices)
            right, left = options
            right_y, right_x = _snap(mask, y, x, right)
            left_y, left_x = _snap(mask, y, x, left)
            right_end = _walk_segment(mask, right_y, right_x, right)
            left_end = _walk_segment(mask, left_y, left_x, left)
            if right_end not in visited:
                stroke.zero = walk_tree(mask, (right_y, right_x), right, visited)
            if left_end not in visited:
                stroke.nonzero = walk_tree(mask, (left_y, left_x), left, visited)
            return stroke

        if kind in ("end", "merge"):
            vertices.append(Vertex(y, x, None))
            return Stroke(vertices)

        # "straight" or "crossing": continue the same stroke through this
        # vertex, adopting its one forward option as the new heading, and
        # snapping onto that leg's true centerline first (see _snap) since
        # the current (y, x) may be a pixel off it.
        heading = options[0]
        y, x = _snap(mask, y, x, heading)


def flatten(stroke: Stroke) -> list[list[Vertex]]:
    """Every walked stroke's vertex list in a tree, main stroke first, depth-first."""
    strokes = [stroke.vertices]
    if stroke.zero is not None:
        strokes.extend(flatten(stroke.zero))
    if stroke.nonzero is not None:
        strokes.extend(flatten(stroke.nonzero))
    return strokes
