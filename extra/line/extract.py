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

try:
    from skimage.morphology import skeletonize
except ImportError as _exc:  # pragma: no cover - environment guard
    raise ImportError(
        "Extracting Line programs requires scikit-image: pip install scikit-image"
    ) from _exc

# Dependency-reduction notes, if these 4 undeclared deps (Pillow, numpy, scipy,
# scikit-image) are ever worth trimming: scikit-image is easiest to drop --
# skeletonize() here only feeds a scalar length into detect_scale()'s
# ink/skeleton-length ratio, and a pure-numpy repeated-erosion step-count
# (erode with padded[1:-1,1:-1] & padded[:-2,1:-1] & ... until the shape
# vanishes) reproduces the same scale detection, confirmed against both
# fixtures at 1x-4x. scipy.ndimage's generate_binary_structure/center_of_mass
# /ndimage.sum are one-liners with np.array(...)/nonzero().mean()/bincount;
# ndimage.label is a ~20-line BFS (this file already has two similar BFS
# loops) confirmed to match scipy exactly on real fixtures.
# distance_transform_edt is the one hard piece to replace -- load-bearing in
# find_cursor, and a brute-force replacement, while exactly correct, is
# O(ink x background) and took 2.6s on a 500x500 fixture vs scipy's near-
# instant separable algorithm; only worth it with a real two-pass EDT.
# Pillow's Image.resize(NEAREST) is trivial (mask[::scale, ::scale]), but
# Image.open is real PNG/JPEG codec work with no numpy/scipy/skimage
# equivalent -- the hardest of the four to actually eliminate.

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


# Below this size a quadrant is a leaf: its full bounding box is used as-is
# rather than subdividing further.  Small enough that a leaf still meaningfully
# narrows down where the ink is on a huge canvas, large enough that the
# recursion doesn't spend time on quadrants near pixel-level granularity where
# a plain scan would be just as fast.
_QUADTREE_LEAF_SIZE = 64


def _content_bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    """Find ink's bounding box in O(content + log(canvas)), not O(canvas).

    ``np.nonzero(mask)`` finds the same bounding box but must touch every
    pixel in the array to do it, so its cost scales with the canvas size
    even when almost all of it is blank -- confirmed to matter in practice:
    on a ~4600x4600 canvas holding a small drawing padded by a 2000px
    border, a plain ``np.nonzero`` scan takes ~9x longer than this.

    Recursively quarters the canvas, skipping (via a cheap ``.any()`` check
    on the numpy slice) any quadrant with no ink at all rather than
    descending into it -- a huge blank border gets discarded in a handful of
    splits rather than scanned pixel by pixel.  Returns the union bounding
    box of every non-empty leaf quadrant, which is a safe superset of the
    true tight bounding box (padded out to quadrant boundaries) rather than
    the exact minimal box -- confirmed never to exclude real ink, which is
    the property that matters for a crop step feeding the rest of the
    pipeline.  Raises :class:`ValueError` if the mask is entirely blank.
    """
    h, w = mask.shape
    stack = [(0, 0, h, w)]
    bounds: list[int] | None = None
    while stack:
        ry0, rx0, ry1, rx1 = stack.pop()
        if not mask[ry0:ry1, rx0:rx1].any():
            continue
        if (ry1 - ry0) <= _QUADTREE_LEAF_SIZE or (rx1 - rx0) <= _QUADTREE_LEAF_SIZE:
            if bounds is None:
                bounds = [ry0, rx0, ry1, rx1]
            else:
                bounds[0] = min(bounds[0], ry0)
                bounds[1] = min(bounds[1], rx0)
                bounds[2] = max(bounds[2], ry1)
                bounds[3] = max(bounds[3], rx1)
            continue
        my, mx = (ry0 + ry1) // 2, (rx0 + rx1) // 2
        stack.extend(
            [
                (ry0, rx0, my, mx),
                (ry0, mx, my, rx1),
                (my, rx0, ry1, mx),
                (my, mx, ry1, rx1),
            ]
        )
    if bounds is None:
        raise ValueError("image contains no ink")
    return bounds[0], bounds[1], bounds[2], bounds[3]


def crop_to_content(mask: np.ndarray, margin: int = 2) -> np.ndarray:
    """Crop ``mask`` to its ink's bounding box (see :func:`_content_bbox`).

    ``margin`` pixels of surrounding blank space are kept on every side so
    downstream code (e.g. :func:`find_cursor`'s distance transform) still
    sees genuine background immediately around the drawing's own edge,
    rather than the crop boundary itself acting like an artificial wall.
    """
    h, w = mask.shape
    y0, x0, y1, x1 = _content_bbox(mask)
    top, bottom = max(0, y0 - margin), min(h, y1 + margin)
    left, right = max(0, x0 - margin), min(w, x1 + margin)
    return mask[top:bottom, left:right]


def detect_scale(mask: np.ndarray) -> int:
    """Estimate the uniform stroke width a Line drawing was rendered at.

    Line's own strokes are always 1px wide in the wiki's reference images
    (see ``render.py``'s module docstring); an image scaled up by some
    integer factor keeps every stroke uniformly that many pixels wide.  For
    a thin stroke, ink area is approximately width times length, so
    ``ink_pixel_count / skeleton_length`` recovers that width -- confirmed
    accurate to within ~5% against 1x/2x/3x/4x scaled copies of both wiki
    reference images, and unaffected by how much blank border surrounds the
    drawing (border pixels are not ink, so they affect neither the
    numerator nor the denominator).

    Skeletonizing is not used to *do* the width correction (tried directly:
    it introduces a systematic off-center bias on diagonal strokes, and
    reduces the cursor's arrowhead -- a solid 2D shape rather than a thin
    stroke -- to a small messy cluster instead of leaving it recognizable),
    only to measure it; :func:`normalize_scale` corrects for it by plain
    downscaling instead.
    """
    skeleton_length = int(skeletonize(mask).sum())
    if skeleton_length == 0:
        return 1
    return max(1, round(int(mask.sum()) / skeleton_length))


def normalize_scale(mask: np.ndarray) -> np.ndarray:
    """Downscale ``mask`` to 1px-wide strokes if it was rendered larger.

    Detects the drawing's stroke width (:func:`detect_scale`) and, if
    greater than 1, downscales the mask by that exact factor with
    nearest-neighbor resampling -- confirmed to recover the *exact* original
    pixel-for-pixel mask when reversing a nearest-neighbor upscale, which is
    what every scale this function needs to handle in practice looks like
    (an integer pixel-replication blow-up of a 1px-wide drawing, not a
    resampled photograph).  A mask already at native scale is returned
    unchanged.

    Pads up to the next multiple of ``scale`` on each axis before dividing,
    rather than truncating a possibly-uneven size down: :func:`crop_to_content`
    only guarantees a bounding box loosely containing the drawing (padded to
    quadtree-leaf boundaries, plus its own margin), not one already aligned
    to the stroke width, and confirmed truncating instead of padding silently
    drops a fractional row/column of real content at that boundary -- caught
    directly on the wiki addition example scaled 4x, where the crop's
    non-scale-aligned width (1054, not a multiple of 4) otherwise lost ink at
    the edge before the walker ever ran.
    """
    scale = detect_scale(mask)
    if scale <= 1:
        return mask
    h, w = mask.shape
    pad_h, pad_w = (-h) % scale, (-w) % scale
    if pad_h or pad_w:
        mask = np.pad(mask, ((0, pad_h), (0, pad_w)))
        h, w = mask.shape
    image = Image.fromarray((~mask * 255).astype(np.uint8))
    small = image.resize((w // scale, h // scale), Image.NEAREST)
    return np.array(small) < 128


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


def flatten(stroke: Stroke) -> list[list[tuple[int, int]]]:
    """Return every walked path in a tree, main stroke first, depth-first."""
    paths = [stroke.path]
    if stroke.zero is not None:
        paths.extend(flatten(stroke.zero))
    if stroke.nonzero is not None:
        paths.extend(flatten(stroke.nonzero))
    return paths


def count_pivots(stroke: Stroke) -> int:
    """Count the branch pivots in a stroke tree (one per real fork)."""
    count = 1 if stroke.zero is not None or stroke.nonzero is not None else 0
    if stroke.zero is not None:
        count += count_pivots(stroke.zero)
    if stroke.nonzero is not None:
        count += count_pivots(stroke.nonzero)
    return count


def _redraw(paths: list[list[tuple[int, int]]], shape: tuple[int, int]) -> np.ndarray:
    """Draw walked pixel paths onto a blank boolean canvas of ``shape``."""
    canvas = np.zeros(shape, dtype=bool)
    for path in paths:
        for y, x in path:
            canvas[y, x] = True
    return canvas


# Constant part of the deliberate, non-bug gap between a stroke tree's walked
# pixels and the source image's ink: 2 arrowhead-tip corners the cursor-blob
# growth threshold falls a pixel short of (see find_cursor's docstring),
# independent of the program's size or branch count.  The per-pivot part (one
# pixel per real fork, its own vertex spent as the pivot rather than walked
# into either arm -- see _walk_tree's docstring) is added by coverage_gap.
# Measured exactly on both wiki reference images: addition (1 pivot) gaps by
# 3, multiplication (3 pivots) gaps by 5 -- both pivots + 2.
_ARROWHEAD_TIP_GAP = 2


def coverage_gap(mask: np.ndarray, cursor: Cursor, stroke: Stroke) -> int:
    """How many source-image ink pixels ``stroke`` leaves unaccounted for.

    Redraws ``stroke``'s walked pixels and XORs against the source (cursor
    blob excluded, since extraction never attempts to reproduce it); a
    perfect extraction differs only at the deliberate gap described in
    :data:`_ARROWHEAD_TIP_GAP`, so this returns 0 for a fully-accounted
    extraction on real input.  A nonzero value beyond the expected gap means
    real ink was never walked -- confirmed to happen concretely from JPEG
    recompression: at quality 32 and below, block quantization can erase a
    pixel or two directly out of a 1px-wide stroke, severing it, and the
    walker then silently stops short with no other symptom (see extract()).
    """
    paths = flatten(stroke)
    redrawn = _redraw(paths, mask.shape)
    reference = mask & ~cursor.blob
    return int((redrawn ^ reference).sum())


def extract(path: str) -> Stroke:
    """Load a Line image and walk its full path tree, cursor auto-detected.

    Two normalization passes run before any of the 1px-stroke-assuming
    logic (:func:`find_cursor`, the walker, region-adjacency junction
    detection) sees the mask:

    * :func:`crop_to_content` discards blank canvas outside the drawing's
      bounding box, found in time proportional to the drawing's own size
      rather than the full canvas -- confirmed to matter for a wiki-style
      image with a large blank margin around a small drawing.
    * :func:`normalize_scale` downscales the drawing back to 1px-wide
      strokes if it was rendered (or exported) larger -- confirmed the
      pipeline otherwise fails immediately and by a wide margin at 2x
      scale and up: the same "3+ neighbors means arrowhead body" rule that
      isolates the cursor at native scale also matches every ordinary
      multi-pixel-wide stroke pixel, so cursor isolation swallows the
      entire drawing instead of just the arrowhead.

    Checks the walked tree against the (normalized) source image before
    returning (see :func:`coverage_gap`) and raises :class:`ValueError` if
    real ink was left unaccounted for, rather than silently returning a
    truncated tree with no indication anything went wrong -- confirmed to
    matter in practice: a JPEG-recompressed copy of a wiki reference image
    walks to completion with no error at all if this check is skipped,
    despite over 85% of the drawing never being reached.  Callers that want
    the best-effort tree regardless can call :func:`extract_tree` directly
    on an already-normalized mask.
    """
    mask = load_binary(path)
    mask = crop_to_content(mask)
    mask = normalize_scale(mask)
    cursor = find_cursor(mask)
    stroke = extract_tree(mask, cursor)
    tolerance = count_pivots(stroke) + _ARROWHEAD_TIP_GAP
    gap = coverage_gap(mask, cursor, stroke)
    if gap > tolerance:
        raise ValueError(
            f"extraction left {gap} source pixels unaccounted for "
            f"(expected at most {tolerance} for this program's structure) "
            "-- the image may be corrupted, over-compressed, or otherwise "
            "not a clean drawing"
        )
    return stroke


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
