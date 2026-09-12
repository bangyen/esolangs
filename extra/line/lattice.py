r"""Extract a Line program's path tree by probing 8-pointed stars at."""

from __future__ import annotations

from dataclasses import dataclass

from mask import Mask

# 8 directions in (dy, dx).
# the same indexing render.py's.
# here and a (dy, dx) heading.
# this module (rather than.
# already depends on this.
# here instead of the two.
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


# Matches render.py's _UNIT:.
# between corners in a Line.
# a single segment is walked.
# the band probe (see module.
# length directly rather than.
# measure a pixel or two off it.
UNIT = 20

# Upper bound on how long a.
# _walk_segment gives up rather.
# unexpected image.
# consecutive `+`/`-` opcodes.
# straight/diagonal run with no.
# render.py's module.
# longest run measures ~60px.
# on the repeat count -- so.
# fixture needs, not a tight.
_MAX_SEGMENT = UNIT * 20


def _band_lit(mask: Mask, y: int, x: int, direction: int) -> bool:
    r"""Whether any of the 3 parallel rays (center + 1px either side) is."""
    pdy, pdx = _DIRS[(direction + 2) % 8]
    return any(_ink(mask, y + pdy * k, x + pdx * k) for k in (-1, 0, 1))


def star(mask: Mask, y: int, x: int, length: int = 15) -> set[int]:
    r"""Which of the 8 directions have a real band segment from this vertex."""
    lit = set()
    for idx, (dy, dx) in enumerate(_DIRS):
        if all(
            _band_lit(mask, y + dy * i, x + dx * i, idx) for i in range(1, length + 1)
        ):
            lit.add(idx)
    return lit


# How many pixels of real,.
# perpendicular-offset.
# direction -- long enough to.
# fixtures all measure >= 19px,.
# neighboring, unrelated leg's.
# a diagonal leg's own body.
# confirmed to falsely satisfy.
# V-notch corner).
_SNAP_CONFIRM = 6


def _snap(mask: Mask, y: int, x: int, direction: int) -> tuple[int, int]:
    r"""Find which of ``(y, x)``'s band offsets is the true centerline for."""
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
    r"""Follow a stroke's own center pixels to this segment's true endpoint."""
    dy, dx = _DIRS[direction]
    py, px = y, x
    for _ in range(_MAX_SEGMENT):
        ny, nx = py + dy, px + dx
        if not _ink(mask, ny, nx):
            return py, px
        py, px = ny, nx
    return py, px


def find_start(
    mask: Mask, approx_y: int, approx_x: int, heading: int
) -> tuple[int, int]:
    r"""Return the path-start vertex for a caller already holding one."""
    del mask, heading
    return approx_y, approx_x


@dataclass
class Vertex:
    r"""One lattice point the walk passes through, plus the heading taken."""

    y: int
    x: int
    heading: int | None


@dataclass
class Stroke:
    r"""One matched straight-through run of lattice vertices, tree-shaped."""

    vertices: list[Vertex]
    zero: Stroke | None = None
    nonzero: Stroke | None = None

    @property
    def end(self) -> tuple[int, int]:
        r"""Return this stroke's final vertex as a plain ``(y, x)`` pair."""
        v = self.vertices[-1]
        return v.y, v.x


def _opposite(idx: int) -> int:
    return (idx + 4) % 8


def _classify(lit: set[int], back: int) -> tuple[str, list[int]]:
    r"""Decide what kind of vertex this is, given its lit directions."""
    rest = lit - {back}
    if not rest:
        return "end", []
    if len(rest) == 1:
        return "straight", list(rest)
    # Rotate relative to the.
    # `back` (the direction arrived.
    # rotating off `back` -- as.
    # arm as its opposite, and.
    # back.
    # and the wiki's rule ("turn.
    # from the cursor's own.
    # that makes `right`/`zero`.
    heading = _opposite(back)
    right, left = (heading + 2) % 8, (heading - 2) % 8
    straight = heading
    if len(lit) == 4 and back in lit and straight in lit:
        return "crossing", [straight]
    if len(rest) == 2 and right in rest and left in rest:
        return "fork", [right, left]
    return "merge", []


def _resnap_dead_end(mask: Mask, y: int, x: int, heading: int) -> tuple[int, int]:
    r"""Recover a vertex :func:`_walk_segment` stopped a column short of."""
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
    r"""Walk a Line image's full path tree via star-probing from ``start``."""
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

        # "straight" or "crossing":.
        # vertex, adopting its one.
        # snapping onto that leg's true.
        # the current (y, x) may be a.
        heading = options[0]
        y, x = _snap(mask, y, x, heading)


def flatten(stroke: Stroke) -> list[list[Vertex]]:
    r"""Every walked stroke's vertex list in a tree, main stroke first,."""
    strokes = [stroke.vertices]
    if stroke.zero is not None:
        strokes.extend(flatten(stroke.zero))
    if stroke.nonzero is not None:
        strokes.extend(flatten(stroke.nonzero))
    return strokes
