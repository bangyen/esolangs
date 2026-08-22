"""Extract a Line program from a rendered PNG.

Counterpart to :mod:`render`.  Line's own spec (https://esolangs.org/wiki/Line)
constrains every drawn segment to one of 8 directions -- 4 cardinal, 4
diagonal at 45 degrees -- confirmed by measuring the wiki's own reference
images (see ``render.py``'s module docstring).  That constraint makes walking
the path far simpler than a general line-drawing-to-graph problem: at an
ordinary pixel exactly one of the 7 non-backward neighbors has ink, so a
greedy walker that always continues in the least-turned available direction
reconstructs a stroke with no skeletonization and no angle classification.

Locating *where* the walker needs to branch, though, is not a local,
per-pixel question: the wiki's own "multiplication" example
(``Lineanim14.png``) contains a real 4-way crossing where a naive
per-pixel shape check cannot tell "two strokes happen to cross here" from
"this is a genuine decision point" using only the few pixels immediately
around it.  This module answers that globally instead of locally, by
flood-filling the image's background into its connected white regions
(4-connectivity, so a diagonal ink stroke correctly separates the regions on
either side of it) and building the region-adjacency graph: two enclosed
regions sharing a short border is exactly where the drawing's topology
branches, independent of any per-pixel angle heuristic.  Verified against
both wiki examples: the addition example flood-fills into 2 regions
(background + 1 enclosed loop), matching its single conditional-turn
instruction; the multiplication example flood-fills into 5 (background + 4
enclosed loops), and the two non-background adjacencies found are compact,
localized borders at exactly the two points a per-pixel walk independently
flagged as junctions.

A junction pixel is only treated as a real conditional-turn branch when
continuing straight ahead is *not* possible -- if the cursor could simply
continue forward through the junction, the crossing strokes are read as an
incidental overlap the cursor passes through untouched, not a decision
point.  (The 4-way crossing in the multiplication example still resolves to
a branch under this rule, because the region-adjacency graph shows it
genuinely encloses its own small region on one side -- there is no ink-free
"straight through" path across it for the direction the cursor arrives in.)

This module does not attempt to classify *which* opcode produced each kink
(that needs the run-length template matching prototyped separately); it
recovers the raw path structure -- an ordered list of pixel coordinates per
stroke, arranged into a tree of branches -- as the layer underneath opcode
recognition.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

try:
    from PIL import Image
except ImportError as _exc:  # pragma: no cover - environment guard
    raise ImportError(
        "Extracting Line programs requires Pillow: pip install Pillow"
    ) from _exc

# 8 directions in (dy, dx) form, indexed 0..7 as N, NE, E, SE, S, SW, W, NW --
# the same indexing render.py's headings would map onto, so a direction index
# here and a (dy, dx) heading there describe the same geometry.
_DIRS: list[tuple[int, int]] = [
    (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)
]

# Cursor arrowhead blobs measured from the wiki's reference images are ~13px
# (a small filled triangle); any solid region above this distance-transform
# threshold is treated as ink thick enough to be the cursor marker rather
# than a 1px-wide path stroke.
_THICK_THRESHOLD = 1.5

# 4-connectivity structuring element for flood-filling background regions --
# see the module docstring for why 4- rather than 8-connectivity matters.
_FOUR_CONN = ndimage.generate_binary_structure(2, 1)


def load_binary(path: str) -> np.ndarray:
    """Load an image as a boolean ink mask (True = black/foreground)."""
    image = Image.open(path).convert("L")
    return np.array(image) < 128


def _ink_neighbor_count(mask: np.ndarray, y: int, x: int) -> int:
    """How many of (y, x)'s 8 neighbors are ink.

    A 1px-wide stroke's interior pixels -- including an ordinary corner,
    which is still just one incoming and one outgoing direction -- have
    exactly 2; a genuine fork has a third arm.
    """
    h, w = mask.shape
    count = 0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and mask[ny, nx]:
                count += 1
    return count


@dataclass
class Cursor:
    """The arrowhead's location, heading, and shape, isolated from a mask."""

    y: float
    x: float
    blob: np.ndarray  # boolean mask, same shape as the source image


# A pixel is "blob-like" (part of the arrowhead's body, not a 1px-wide path
# stroke) if it has this many ink neighbors in its 3x3 neighborhood -- a
# stroke's interior pixels have exactly 2 (the one before, the one after);
# the triangle's outline and tips have 3+.
_BLOB_NEIGHBOR_MIN = 3

# Fraction of its own bounding box a real arrowhead blob fills.  Measured by
# rendering render.py's own arrowhead at all 8 possible headings: 0.41-0.55
# depending on rotation (a diagonal heading's axis-aligned bbox is larger
# relative to the triangle it bounds).  The bracket here is deliberately
# wide of that measured range -- it exists to catch a blob that is not
# triangular at all (a solid square rejects at 1.0; two crossing strokes at
# a shallow angle either fail _THICK_THRESHOLD entirely or produce a long
# thin sliver well under 0.25), not to pick between two genuinely
# arrowhead-shaped candidates, which this check cannot and does not attempt
# to disambiguate (see find_cursor's docstring).
_FILL_RATIO_RANGE = (0.25, 0.75)


def _fill_ratio(blob: np.ndarray) -> float:
    """Fraction of ``blob``'s own bounding box that is filled."""
    ys, xs = np.nonzero(blob)
    height = int(ys.max() - ys.min()) + 1
    width = int(xs.max() - xs.min()) + 1
    return float(blob.sum()) / (height * width)


def find_cursor(mask: np.ndarray) -> Cursor:
    """Isolate the whole arrowhead shape via distance transform + growth.

    The arrowhead is the only solid (multi-pixel-thick) region in a
    correctly-drawn Line image; every path stroke is 1px wide.  The distance
    transform picks out its thick *interior*, which is enough to locate and
    identify it (the largest such region, so a stray thick artifact
    elsewhere in the image does not get mistaken for the cursor) but is
    narrower than its full silhouette -- the outline and pointed tips are
    only 1px wide and would be left behind as orphaned ink if only the
    thick core were stripped from the mask (confirmed: doing so left a
    13-pixel triangular stub that the region-adjacency junction check then
    misread as a real branch).

    ``blob`` grows the thick core outward through ink, admitting a
    neighboring pixel only while it is itself blob-like (see
    ``_BLOB_NEIGHBOR_MIN``) rather than by a fixed dilation radius or plain
    connected-component flood fill -- both were tried first: a fixed radius
    either left outline pixels behind or, sized larger, ate into the real
    path stroke nearby, and connected-component labeling swallowed the
    entire drawing, since the arrow's tip touches the path by construction.
    Gating growth on local pixel density stops naturally at the point the
    silhouette narrows down to the 1px-wide stroke leaving it -- the same
    place a human eye would call "where the arrowhead ends" -- typically
    within a pixel of the triangle's true boundary.

    "Largest thick region" is otherwise an unchecked assumption: a drawing
    with any other filled shape, or two strokes crossing at a shallow
    enough angle to read as locally thick, would silently make this pick
    the wrong region with no error (confirmed with a synthetic two-triangle
    image -- it deterministically returns whichever triangle is bigger,
    correct or not).  The size ranking cannot be fixed by shape alone when
    two candidates are both genuinely triangular; what a shape check *can*
    catch is the winning candidate not looking like an arrowhead at all
    (see :data:`_FILL_RATIO_RANGE`), so that case raises instead of
    returning a silently wrong cursor.
    """
    dist = ndimage.distance_transform_edt(mask)
    thick = dist > _THICK_THRESHOLD
    if not thick.any():
        raise ValueError("no cursor (thick/filled region) found in image")
    thick_labeled, thick_count = ndimage.label(thick)
    sizes = ndimage.sum(thick, thick_labeled, range(1, thick_count + 1))
    cursor_label = int(np.argmax(sizes)) + 1
    core = thick_labeled == cursor_label
    cy, cx = ndimage.center_of_mass(core)

    h, w = mask.shape
    visited = {(int(y), int(x)) for y, x in zip(*np.nonzero(core), strict=True)}
    frontier = list(visited)
    while frontier:
        y, x = frontier.pop()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                ny, nx = y + dy, x + dx
                if (ny, nx) in visited:
                    continue
                if (
                    0 <= ny < h
                    and 0 <= nx < w
                    and mask[ny, nx]
                    and _ink_neighbor_count(mask, ny, nx) >= _BLOB_NEIGHBOR_MIN
                ):
                    visited.add((ny, nx))
                    frontier.append((ny, nx))

    blob = np.zeros_like(mask)
    for y, x in visited:
        blob[y, x] = True

    ratio = _fill_ratio(blob)
    low, high = _FILL_RATIO_RANGE
    if not low <= ratio <= high:
        raise ValueError(
            f"largest thick region does not look like an arrowhead "
            f"(fill ratio {ratio:.2f}, expected {low:.2f}-{high:.2f})"
        )
    return Cursor(float(cy), float(cx), blob)


@dataclass
class RegionMap:
    """The background flood-filled into connected regions, plus adjacency.

    ``labels`` gives each background pixel's region id (0 for ink).
    ``background`` is the id of the single largest region -- the drawing's
    exterior.  ``junctions`` maps each ink pixel that borders 2+ distinct
    regions (background included -- a plain stroke, even at an ordinary
    kink, only ever has the same single region, usually background, on both
    sides) to the sorted tuple of region ids it separates: these are the
    image's real structural decision points (see module docstring).
    """

    labels: np.ndarray
    background: int
    junctions: dict[tuple[int, int], tuple[int, ...]]


def build_region_map(mask: np.ndarray) -> RegionMap:
    """Flood-fill the background and locate real (non-background) junctions."""
    white = ~mask
    labels, count = ndimage.label(white, structure=_FOUR_CONN)
    if count == 0:
        return RegionMap(labels, 0, {})
    sizes = ndimage.sum(white, labels, range(1, count + 1))
    background = int(np.argmax(sizes)) + 1

    h, w = mask.shape
    ink_ys, ink_xs = np.nonzero(mask)
    junctions: dict[tuple[int, int], set[int]] = {}
    for y, x in zip(ink_ys.tolist(), ink_xs.tolist(), strict=True):
        touching = set()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and white[ny, nx]:
                touching.add(int(labels[ny, nx]))
        # A pixel bordering 2+ distinct regions (background included) sits
        # between two areas that are not connected to each other except
        # through ink -- an ordinary stroke, even at a kink, borders only
        # one region (the same background on both sides), so this does not
        # fire on plain corners.  Background is excluded from the *count*
        # of non-background regions elsewhere, but a background/enclosed-
        # region boundary is just as real a branch as two enclosed regions
        # meeting (e.g. a T-junction's stem separates an enclosed loop from
        # open background, not from another loop) -- see module docstring.
        if len(touching) >= 2:
            junctions[(y, x)] = touching

    sorted_junctions = {k: tuple(sorted(v)) for k, v in junctions.items()}
    return RegionMap(labels, background, sorted_junctions)


def _ink(mask: np.ndarray, y: int, x: int) -> bool:
    h, w = mask.shape
    return 0 <= y < h and 0 <= x < w and bool(mask[y, x])


def _turn_order(heading: int) -> list[int]:
    """Direction indices ordered by how little they turn from ``heading``.

    Straight ahead first, then the smallest turns either way, ending at a
    full reversal -- so a greedy walk prefers continuing the current stroke
    over jumping to an unrelated one that happens to touch it.
    """
    return sorted(range(8), key=lambda i: min((i - heading) % 8, (heading - i) % 8))


def _is_branch_pivot(region_map: RegionMap, y: int, x: int, heading: int) -> bool:
    """Whether (y, x), arrived at ``heading``, may be a conditional-turn pivot.

    ``region_map.junctions`` (see :func:`build_region_map`) marks every pixel
    bordering 2+ distinct regions -- but that includes the *entire* stem
    leading up to a T-junction, not just its tip: each pixel along the stem
    borders the same two regions the bar at the top does, one on each side,
    all the way down.  A per-pixel run-length check (require N ink pixels
    straight ahead) was tried first and does not cleanly separate "still on
    the stem" from "at the tip" either, because the perpendicular bar itself
    is only 1px thick and breaks any fixed-length run check right where the
    branch actually is, not before it.  The reliable signal instead: walking
    along the stem, the pixel straight ahead is *also* in ``junctions``; at
    the true tip it is not, since the bar runs perpendicular rather than
    parallel to the region boundary there.

    This is a *candidate* test only -- it also fires on an ordinary corner
    where the boundary between the same two regions simply changes direction
    (confirmed: the point where the addition example's top bar bends into a
    diagonal has exactly this shape, despite being a plain turn).  Distin-
    guishing a real fork from a plain corner needs to check whether the
    pivot *actually has two walkable arms* (see :func:`_walk_tree`), which a
    local pixel-shape test cannot answer on its own -- an acute diagonal
    corner can present 3+ ink neighbors in its 3x3 neighborhood purely from
    one continuing stroke bending sharply, with no second arm at all
    (confirmed against the addition example's V-shaped notch).
    """
    if (y, x) not in region_map.junctions:
        return False
    dy, dx = _DIRS[heading]
    return (y + dy, x + dx) not in region_map.junctions


def _walk(
    mask: np.ndarray,
    region_map: RegionMap,
    start: tuple[int, int],
    heading: int,
    visited: set[tuple[int, int]],
    crossings: set[tuple[int, int]],
    *,
    check_start: bool = True,
) -> list[tuple[int, int]]:
    """Greedily follow ink from ``start``, preferring the smallest turn.

    Stops when it runs out of unvisited ink, or reaches a candidate branch
    pivot (see :func:`_is_branch_pivot` -- confirming it as a real fork
    rather than a plain corner is :func:`_walk_tree`'s job, since that needs
    to actually check both perpendicular arms for ink).  ``visited`` is
    shared across every walk in a single :func:`extract_tree` call, so no
    stroke -- main path or any branch arm -- can wander back onto one
    already covered; a stroke can rejoin ink it already walked from any
    angle, most concretely a branch arm walking back onto the stem leading
    into that same branch, which a single-step "don't reverse" check would
    not catch.

    ``crossings`` (pixels :func:`_walk_tree` has confirmed are noop
    straight-through crossings, not real branches -- see its docstring) are
    the one exception: unlike ordinary stroke pixels, a crossing is by
    definition where two *independent* strokes legitimately overlap, so a
    second arm passing through later must still be able to step onto it even
    though the first arm already marked it visited.  Without this, whichever
    arm reaches a crossing first silently blocks every other arm that also
    needs to pass through it, truncating them at the crossing instead of
    letting them continue on the other side.

    ``check_start=False`` skips the pivot check on ``start`` itself for one
    iteration: :func:`_walk_tree` uses this to resume a walk from a pixel it
    already determined is *not* a real fork (a plain corner that merely
    looked like a candidate pivot), without re-triggering the same check
    immediately and never making progress.
    """
    y, x = start
    path = [(y, x)]
    visited.add((y, x))
    first = True
    while True:
        if (check_start or not first) and _is_branch_pivot(region_map, y, x, heading):
            return path
        first = False
        found = None
        for idx in _turn_order(heading):
            dy, dx = _DIRS[idx]
            ny, nx = y + dy, x + dx
            if (ny, nx) in visited and (ny, nx) not in crossings:
                continue
            if _ink(mask, ny, nx):
                found = (idx, ny, nx)
                break
        if found is None:
            return path
        heading, y, x = found
        path.append((y, x))
        visited.add((y, x))


@dataclass
class Stroke:
    """One walked segment: a path, ending either free or at a branch.

    ``zero``/``nonzero`` are the two continuations of a conditional-turn
    instruction met at the end of ``path`` (right turn on a zero cell, left
    turn otherwise, per the wiki's "turn right if the current cell is 0,
    otherwise turn left"); both are ``None`` for a stroke that ends free
    (ink simply runs out) rather than at a branch.
    """

    path: list[tuple[int, int]]
    zero: Stroke | None = None
    nonzero: Stroke | None = None

    @property
    def end(self) -> tuple[int, int]:
        """The pixel this stroke's path stops at."""
        return self.path[-1]

    @property
    def heading(self) -> int:
        """Direction of travel at the end of this stroke."""
        return _stroke_heading(self.path)


def _stroke_heading(path: list[tuple[int, int]]) -> int:
    """Direction of travel at the end of an ordered pixel path."""
    if len(path) < 2:
        return 0
    (py, px), (ey, ex) = path[-2], path[-1]
    return _DIRS.index((ey - py, ex - px))


def _walk_tree(
    mask: np.ndarray,
    region_map: RegionMap,
    start: tuple[int, int],
    heading: int,
    visited: set[tuple[int, int]],
    crossings: set[tuple[int, int]],
) -> Stroke:
    """Walk one stroke, then recurse into both arms of any branch it hits.

    Handles an arbitrary number of nested branches (unlike following a
    single conditional turn), since the wiki's multiplication example -- a
    program that needs a loop, hence more than one conditional turn --
    contains several.

    A stroke stops at a candidate pivot (:func:`_is_branch_pivot`), but that
    test alone cannot tell a real fork from an ordinary corner where the
    region boundary just changes direction (confirmed against the addition
    example's V-shaped notch, which is a candidate pivot with no second arm
    at all).  The real test is whether *both* of the pivot's perpendicular
    directions actually have ink: a true conditional turn's bar extends both
    ways from the stem (confirmed at the addition example's real T), while a
    plain corner only ever has ink continuing in one direction, and it need
    not be either perpendicular option -- so a pivot that fails this test is
    folded back into a single continued walk from the pivot itself, trying
    every direction (not just the two perpendicular ones), rather than
    silently stopping the stroke short.
    """
    path = list(_walk(mask, region_map, start, heading, visited, crossings))
    while True:
        end, end_heading = path[-1], _stroke_heading(path)
        # ``_walk`` only ever stops on exhausted ink or a candidate pivot
        # (see its docstring), so re-checking here is just asking which of
        # the two just happened -- no risk of re-triggering the same pivot
        # check ``_walk`` already resolved for this stopping point.
        if not _is_branch_pivot(region_map, *end, end_heading):
            return Stroke(path)

        # The branch's two arms lead off the perpendicular bar one step
        # ahead of the stem's tip (``end``), not off the tip itself:
        # geometrically the bar the stem meets sits one pixel further in the
        # direction of travel (e.g. the addition example's stem tip is at
        # row 58, and the bar it meets is at row 57), so the arms' starting
        # points are perpendicular steps from *that* pivot pixel, not from
        # ``end``.
        fdy, fdx = _DIRS[end_heading]
        pivot = (end[0] + fdy, end[1] + fdx)
        is_real_fork = False
        pivot_available = pivot not in visited or pivot in crossings
        if pivot_available and _ink(mask, *pivot):
            # A 4-way crossing -- ink continues straight past the pivot, in
            # addition to both perpendicular directions having ink -- is
            # read as an incidental overlap the cursor drives straight
            # through untouched, not a second decision point: a Line
            # program only has one conditional-turn instruction, so a
            # genuine second branch here would be redundant with whichever
            # one already produced this arm, and the wiki's own
            # multiplication example needs only a single conditional turn
            # for its multiply loop.  Confirmed against that example: its
            # one real T-junction is upstream of this crossing, and the
            # crossing itself has ink continuing straight through in
            # addition to both perpendicular arms.
            #
            # A confirmed crossing is recorded in ``crossings`` so that a
            # *second*, independent arm reaching the same pixel later can
            # still pass through it -- unlike an ordinary stroke pixel,
            # which is legitimately single-use, a crossing is by definition
            # where two unrelated strokes overlap, and the first arm to
            # reach it must not permanently claim it against the other.
            past_dy, past_dx = _DIRS[end_heading]
            straight_open = _ink(mask, pivot[0] + past_dy, pivot[1] + past_dx)
            if straight_open:
                crossings.add(pivot)
            else:
                right = (end_heading + 2) % 8
                left = (end_heading - 2) % 8
                dy, dx = _DIRS[right]
                right_start = (pivot[0] + dy, pivot[1] + dx)
                dy, dx = _DIRS[left]
                left_start = (pivot[0] + dy, pivot[1] + dx)
                is_real_fork = _ink(mask, *right_start) and _ink(mask, *left_start)

        if is_real_fork:
            stroke = Stroke(path)
            visited.add(pivot)
            if right_start not in visited:
                stroke.zero = _walk_tree(
                    mask, region_map, right_start, right, visited, crossings
                )
            if left_start not in visited:
                stroke.nonzero = _walk_tree(
                    mask, region_map, left_start, left, visited, crossings
                )
            return stroke

        # Not a real fork: keep walking the same stroke from ``end`` instead
        # of stopping it here, matching what an ordinary corner (see module
        # docstring's V-notch case) would get if it had never been mistaken
        # for a candidate pivot in the first place.  ``check_start=False``
        # skips re-triggering the same pivot check immediately; the normal
        # smallest-turn search in ``_walk`` still finds whatever direction
        # the corner actually continues in, which need not be
        # ``end_heading`` at all -- the addition example's bar-into-diagonal
        # bend continues at a different angle entirely.
        more = _walk(
            mask, region_map, end, end_heading, visited, crossings, check_start=False
        )
        if len(more) <= 1:
            return Stroke(path)  # no further ink; nothing more to walk
        path.extend(more[1:])


def extract_tree(mask: np.ndarray, cursor: Cursor, start_heading: int = 0) -> Stroke:
    """Walk a Line image's full path tree from the cursor.

    ``start_heading`` is a direction index into ``_DIRS`` (default 0 = N,
    "up" -- the heading every wiki example starts from, arrow pointing up
    from the bottom of the drawing).
    """
    stripped = mask & ~cursor.blob
    region_map = build_region_map(stripped)
    ys, xs = np.nonzero(stripped)
    if ys.size == 0:
        raise ValueError("no path pixels found outside the cursor blob")
    dists = (ys - cursor.y) ** 2 + (xs - cursor.x) ** 2
    start = (int(ys[np.argmin(dists)]), int(xs[np.argmin(dists)]))
    return _walk_tree(stripped, region_map, start, start_heading, set(), set())


def extract(path: str) -> Stroke:
    """Load a Line image and walk its full path tree, cursor auto-detected."""
    mask = load_binary(path)
    cursor = find_cursor(mask)
    return extract_tree(mask, cursor)


def flatten(stroke: Stroke) -> list[list[tuple[int, int]]]:
    """Return every walked path in a tree, main stroke first, depth-first."""
    paths = [stroke.path]
    if stroke.zero is not None:
        paths.extend(flatten(stroke.zero))
    if stroke.nonzero is not None:
        paths.extend(flatten(stroke.nonzero))
    return paths


if __name__ == "__main__":
    import sys

    def _describe(stroke: Stroke, indent: str = "") -> None:
        print(f"{indent}stroke: {len(stroke.path)} px, end={stroke.end}")
        if stroke.zero is not None:
            print(f"{indent}  zero ->")
            _describe(stroke.zero, indent + "    ")
        if stroke.nonzero is not None:
            print(f"{indent}  nonzero ->")
            _describe(stroke.nonzero, indent + "    ")

    result = extract(sys.argv[1])
    _describe(result)
    total = sum(len(p) for p in flatten(result))
    print(f"total walked: {total} px")
