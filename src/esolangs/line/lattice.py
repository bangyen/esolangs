"""Extract a Line program's path tree by probing 8-pointed stars at each vertex.

Replaces :mod:`extract`'s pixel walker, whose one structural gap was a
merge -- one stroke's last leg running into another's ink with no
background pixel between, which three local fixes each broke on a new
bend.  At every vertex, probe all 8 compass directions and count the lit
ones: 2 is a bend (continue), 3 is a fork or an incidental merge (both
stop the stroke), 4 is a crossing (pass straight through).  A real fork's
two other directions are the pair perpendicular to arrival (the wiki's
T-branch); a merge's are not.  ``multiplication.png``'s hand-decoded
``(194, 228)`` merge reads exactly 3.

The probe is a 3-pixel band (the ray plus one each side): a single ray
missed segments a pixel short of the unit and vertices a pixel off the
true corner (``addition.png``'s T-bar sits one row above where the stem's
path data ends).  Length is read where all three rays lose ink at once.
Over ~90 direction-change vertices in both fixtures every bend reads 2,
every fork or merge 3, and the only 1 is a genuine dead end.
"""

from __future__ import annotations

from dataclasses import dataclass

from .mask import Mask

# (dy, dx) for N, NE, E, SE, S, SW, W, NW, matching render.py's headings.
# Owned here so extract.py imports it rather than the two importing each other.
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


def _ink(mask: Mask, y: int, x: int) -> bool:
    h, w = mask.shape
    return 0 <= y < h and 0 <= x < w and bool(mask[y, x])


# render.py's _UNIT.  Only the probe's scale; the band reads real lengths,
# which run a pixel or two off it, and no run is capped at a multiple of it.
UNIT = 20

# Stay one quarter-unit inside the nominal corner spacing.  At UNIT=20 this
# preserves the measured 15px probe; deriving it keeps the same clearance when
# a smaller lattice unit is introduced.
_PROBE_LENGTH = max(1, UNIT * 3 // 4)


def _band_lit(mask: Mask, y: int, x: int, direction: int) -> bool:
    """Whether any of the 3 parallel rays (center + 1px either side) is ink."""
    pdy, pdx = _DIRS[(direction + 2) % 8]
    return any(_ink(mask, y + pdy * k, x + pdx * k) for k in (-1, 0, 1))


def star(mask: Mask, y: int, x: int, length: int = _PROBE_LENGTH) -> set[int]:
    """Which of the 8 directions have a real band segment from this vertex.

    ``length`` need only be shorter than the shortest real segment (all
    >= 19px on both fixtures); the default is three quarters of :data:`UNIT`.
    """
    lit = set()
    for idx, (dy, dx) in enumerate(_DIRS):
        if all(
            _band_lit(mask, y + dy * i, x + dx * i, idx) for i in range(1, length + 1)
        ):
            lit.add(idx)
    return lit


# Ink depth _snap requires before trusting an offset: a neighbouring leg
# brushing past satisfied a 1-pixel check at addition.png's V-notch.
_SNAP_CONFIRM = 6


def _snap(mask: Mask, y: int, x: int, direction: int) -> tuple[int, int]:
    """Find which of ``(y, x)``'s band offsets is the true centerline for ``direction``.

    A recorded vertex can be a pixel off the true corner of the leg leaving
    it (a diagonal touching down one row below the bar it turns into).
    Snapping once, before walking a chosen direction, avoids the overshoot
    the band would cause per step; several pixels of ink are required, since
    a nearby leg can brush past for one.
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


def _walk_segment(mask: Mask, y: int, x: int, direction: int) -> tuple[int, int]:
    """Follow a stroke's own center pixels to this segment's true endpoint.

    Advances while the exact next pixel is ink -- not the band, which
    overshoots onto a neighbouring leg within its lateral reach.  Runs to
    the run's real end, with no length ceiling: it terminates because every
    step moves one pixel closer to an edge and off-mask reads as
    background.  A ceiling (it was ``UNIT * 20`` = 400px) *invents a vertex*
    mid-run, and ``_classify`` then reads whatever sits there -- 400px up
    ``+[>++++++++[>+<-]<-]>>.``'s stem sits a loop-back's merge point, so
    the walk ended there, 4958 of 5577 pixels short.
    """
    dy, dx = _DIRS[direction]
    py, px = y, x
    while True:
        ny, nx = py + dy, px + dx
        if not _ink(mask, ny, nx):
            return py, px
        py, px = ny, nx


def find_start(
    mask: Mask, approx_y: int, approx_x: int, heading: int
) -> tuple[int, int]:
    """Return the path-start vertex for a caller already holding one.

    :func:`extract.find_cursor` lands on the arrowhead's tip on both fixtures;
    this is a named passthrough, ``mask``/``heading`` for interface symmetry.
    """
    del mask, heading
    return approx_y, approx_x


@dataclass
class Vertex:
    """One lattice point the walk passes through, plus the heading taken.

    ``heading`` is the :data:`extract._DIRS` index travelled *away*; ``None``
    at a stroke's final vertex.
    """

    y: int
    x: int
    heading: int | None


@dataclass
class Stroke:
    """One matched straight-through run of lattice vertices, tree-shaped.

    Mirrors :class:`extract.Stroke` with on-lattice :class:`Vertex` objects
    rather than a dense pixel path.
    """

    vertices: list[Vertex]
    zero: Stroke | None = None
    nonzero: Stroke | None = None

    @property
    def end(self) -> tuple[int, int]:
        """Return this stroke's final vertex as a plain ``(y, x)`` pair."""
        v = self.vertices[-1]
        return v.y, v.x


def _opposite(idx: int) -> int:
    return (idx + 4) % 8


def _classify(lit: set[int], back: int) -> tuple[str, list[int]]:
    """Decide what kind of vertex this is, given its lit directions.

    ``lit`` includes ``back``.  ``"end"``: only ``back``.  ``"straight"``:
    one more.  ``"crossing"``: 4 lit including straight ahead; pass through.
    ``"fork"``: 3 lit, the other two ``back +/- 2``; ``options`` is those,
    right (zero) first.  ``"merge"``: 3 lit otherwise; stops like ``"end"``,
    kept distinct for diagnostics.
    """
    rest = lit - {back}
    if not rest:
        return "end", []
    if len(rest) == 1:
        return "straight", list(rest)
    # Rotate off the *heading*, not `back` (180 degrees out, which once
    # named every arm as its opposite): the wiki's rule and render.py's
    # turns are in the cursor's own frame.
    heading = _opposite(back)
    right, left = (heading + 2) % 8, (heading - 2) % 8
    straight = heading
    if len(lit) == 4 and back in lit and straight in lit:
        return "crossing", [straight]
    if len(rest) == 2 and right in rest and left in rest:
        return "fork", [right, left]
    return "merge", []


def _resnap_dead_end(mask: Mask, y: int, x: int, heading: int) -> tuple[int, int]:
    """Recover a vertex :func:`_walk_segment` stopped a column short of.

    The walk advances in one direction, so a corner one pixel over on the
    perpendicular axis can read as a dead end: ``multiplication.png``'s S
    segment stopped at ``(72, 267)`` (``{N}``) one column short of the
    NE-turning ``(72, 268)`` (``{N, NE}``), silently dropping a ~460px branch
    (caught by comparing coverage against :mod:`extract`'s walker).  Only
    called when ``star`` already reads a dead end; tries both perpendicular
    neighbours and returns the first whose star is more than ``back``.
    """
    back = _opposite(heading)
    pdy, pdx = _DIRS[(heading + 2) % 8]
    for k in (-1, 1):
        cy, cx = y + pdy * k, x + pdx * k
        if star(mask, cy, cx) - {back}:
            return cy, cx
    return y, x


def walk_tree(
    mask: Mask,
    start: tuple[int, int],
    heading: int,
    visited: set[tuple[int, int]] | None = None,
) -> Stroke:
    """Walk a Line image's full path tree via star-probing from ``start``.

    Continues through ``"straight"``/``"crossing"``, stops at
    ``"end"``/``"merge"``, recurses into both arms of a ``"fork"``.
    ``visited`` keeps an arm off vertices an earlier arm walked (two arms of
    one fork can reach the same far vertex on a looping program).
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
