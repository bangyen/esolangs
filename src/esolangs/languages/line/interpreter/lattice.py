"""Extract a Line program's path tree by probing 8-pointed stars at each vertex.

At every vertex, probe all 8 compass directions and count the lit ones:
2 is a bend (continue), 3 is a fork or a merge (both stop the stroke),
4 is a crossing (pass straight through).  A fork's two other directions
are the pair perpendicular to the arrival heading (the wiki's T-branch);
a merge's are not.  The probe is a 3-pixel band (the ray plus one each
side), so vertices a pixel off the true corner still read their
segments; length is read where all three rays lose ink at once.
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
    return (
        0 <= y < mask.height and 0 <= x < mask.width and bool((mask.rows[y] >> x) & 1)
    )


# render.py's _UNIT.  Only the probe's scale; the band reads real lengths,
# which run a pixel or two off it, and no run is capped at a multiple of it.
UNIT = 20


# Stay one quarter-unit inside the nominal corner spacing.  At UNIT=20 this
# preserves the measured 15px probe; deriving it keeps the same clearance when
# a smaller lattice unit is introduced.
def _probe_length(unit: int) -> int:
    """Return how far a probe reaches: three quarters of a lattice unit."""
    return max(1, (3 * unit) // 4)


_PROBE_LENGTH = _probe_length(UNIT)


def _band_lit(mask: Mask, y: int, x: int, direction: int) -> bool:
    """Whether any of the 3 parallel rays (center + 1px either side) is ink."""
    pdy, pdx = _DIRS[(direction + 2) % 8]
    return (
        _ink(mask, y - pdy, x - pdx) or _ink(mask, y, x) or _ink(mask, y + pdy, x + pdx)
    )


def star(mask: Mask, y: int, x: int, length: int = _PROBE_LENGTH) -> set[int]:
    """Which of the 8 directions have a real band segment from this vertex.

    ``length`` need only be shorter than the shortest real segment; the
    default is three quarters of :data:`UNIT`.
    """
    lit = set()
    for idx, (dy, dx) in enumerate(_DIRS):
        if all(
            _band_lit(mask, y + dy * i, x + dx * i, idx) for i in range(1, length + 1)
        ):
            lit.add(idx)
    return lit


# Ink depth _snap requires before trusting an offset: a single pixel of ink
# can be a nearby leg brushing past, not the true centerline.
_SNAP_CONFIRM = 6


def _snap(
    mask: Mask, y: int, x: int, direction: int, unit: int = UNIT
) -> tuple[int, int]:
    """Find which of ``(y, x)``'s band offsets is the true centerline for ``direction``.

    A recorded vertex can be a pixel off the true corner of the leg leaving
    it, which would overshoot the band if walked step by step.  Snapping
    once onto that leg's centerline first avoids this; several pixels of
    ink are required in the chosen direction, since a nearby leg can brush
    past for one.
    """
    dy, dx = _DIRS[direction]
    pdy, pdx = _DIRS[(direction + 2) % 8]
    for k in (0, 1, -1):
        cy, cx = y + pdy * k, x + pdx * k
        if all(
            _ink(mask, cy + dy * i, cx + dx * i)
            for i in range(1, max(1, _SNAP_CONFIRM * unit // UNIT) + 1)
        ):
            return cy, cx
    return y, x


def _walk_segment(mask: Mask, y: int, x: int, direction: int) -> tuple[int, int]:
    """Follow a stroke's own center pixels to this segment's true endpoint.

    Advances while the exact next pixel is ink -- not the band, which
    overshoots onto a neighbouring leg within its lateral reach.  Runs to
    the segment's real end, with no length ceiling: it terminates because
    every step moves one pixel closer to an edge and off-mask reads as
    background.
    """
    dy, dx = _DIRS[direction]
    py, px = y, x
    while True:
        ny, nx = py + dy, px + dx
        if not _ink(mask, ny, nx):
            return py, px
        py, px = ny, nx


@dataclass
class Vertex:
    """One lattice point the walk passes through, plus the heading taken.

    ``heading`` is the :data:`_DIRS` index travelled *away*; ``None``
    at a stroke's final vertex.
    """

    y: int
    x: int
    heading: int | None


@dataclass
class Stroke:
    """One matched straight-through run of lattice vertices, tree-shaped.

    Built from on-lattice :class:`Vertex` objects rather than a dense pixel
    path; ``extract.Stroke`` is this class.
    """

    vertices: list[Vertex]
    zero: Stroke | None = None
    nonzero: Stroke | None = None
    unit: int = UNIT

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
    # Rotate off the *heading*, not `back` (180 degrees out): the wiki's
    # rule and render.py's turns are in the cursor's own frame.
    heading = _opposite(back)
    right, left = (heading + 2) % 8, (heading - 2) % 8
    straight = heading
    if len(lit) == 4 and back in lit and straight in lit:
        return "crossing", [straight]
    if len(rest) == 2 and right in rest and left in rest:
        return "fork", [right, left]
    return "merge", []


def _resnap_dead_end(
    mask: Mask, y: int, x: int, heading: int, unit: int = UNIT
) -> tuple[int, int]:
    """Recover a vertex :func:`_walk_segment` stopped one column short of.

    The walk advances in one direction, so a corner one pixel over on the
    perpendicular axis can read as a dead end and silently drop a branch.
    Only called when ``star`` already reads a dead end; tries both
    perpendicular neighbours and returns the first whose star shows more
    than ``back``.
    """
    back = _opposite(heading)
    pdy, pdx = _DIRS[(heading + 2) % 8]
    for k in (-1, 1):
        cy, cx = y + pdy * k, x + pdx * k
        if star(mask, cy, cx, _probe_length(unit)) - {back}:
            return cy, cx
    return y, x


def walk_tree(
    mask: Mask,
    start: tuple[int, int],
    heading: int,
    visited: set[tuple[int, int]] | None = None,
    *,
    unit: int = UNIT,
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
            return Stroke(vertices, unit=unit)

        back = _opposite(heading)
        lit = star(mask, y, x, _probe_length(unit))
        if not lit - {back}:
            y, x = _resnap_dead_end(mask, y, x, heading, unit)
            lit = star(mask, y, x, _probe_length(unit))
        visited.add((y, x))
        kind, options = _classify(lit, back)

        if kind == "fork":
            vertices.append(Vertex(y, x, None))
            stroke = Stroke(vertices, unit=unit)
            right, left = options
            right_y, right_x = _snap(mask, y, x, right, unit)
            left_y, left_x = _snap(mask, y, x, left, unit)
            right_end = _walk_segment(mask, right_y, right_x, right)
            left_end = _walk_segment(mask, left_y, left_x, left)
            if right_end not in visited:
                stroke.zero = walk_tree(
                    mask, (right_y, right_x), right, visited, unit=unit
                )
            if left_end not in visited:
                stroke.nonzero = walk_tree(
                    mask, (left_y, left_x), left, visited, unit=unit
                )
            return stroke

        if kind in ("end", "merge"):
            vertices.append(Vertex(y, x, None))
            return Stroke(vertices, unit=unit)

        # "straight" or "crossing": continue the same stroke through this
        # vertex, adopting its one forward option as the new heading, and
        # snapping onto that leg's true centerline first (see _snap) since
        # the current (y, x) may be a pixel off it.
        heading = options[0]
        y, x = _snap(mask, y, x, heading, unit)


def flatten(stroke: Stroke) -> list[list[Vertex]]:
    """Every walked stroke's vertex list in a tree, main stroke first, depth-first."""
    strokes = [stroke.vertices]
    if stroke.zero is not None:
        strokes.extend(flatten(stroke.zero))
    if stroke.nonzero is not None:
        strokes.extend(flatten(stroke.nonzero))
    return strokes
