"""Extract a Line program from a rendered PNG.

Counterpart to :mod:`render`.  Line's own spec (https://esolangs.org/wiki/Line)
constrains every drawn segment to one of 8 directions -- 4 cardinal, 4
diagonal at 45 degrees -- confirmed by measuring the wiki's own reference
images (see ``render.py``'s module docstring).

This module handles everything around the walk itself: loading and
normalizing a source image to a clean 1px-stroke boolean mask
(:func:`load_binary`, :func:`crop_to_content`, :func:`normalize_scale`),
isolating the cursor's arrowhead to find the path's starting point
(:func:`find_cursor`), and, once walked, classifying each stroke's kinks
into opcodes (:func:`classify_ops`) and verifying the walk accounted for
all the source image's ink (:func:`coverage_gap`).

The walk itself -- finding *where* the path tree branches, which is not a
local per-pixel question (the wiki's own "multiplication" example contains a
real 4-way crossing a naive per-pixel shape check cannot tell apart from a
genuine decision point using only the pixels immediately around it) -- lives
in :mod:`lattice` instead, whose star-probe walker replaced an earlier
region-adjacency approach in this module (see its module docstring, and
``WIP.md``, for why: a merge, where one stroke's last leg runs straight into
a *different*, already-drawn stroke's ink with no separating background
pixel, could not be told apart from an ordinary continuation by that walker,
and three attempts at a local pixel-geometry fix were each tried and
reverted).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import lattice, png
from . import mask as mask_module
from .lattice import _DIRS, _ink
from .mask import Mask

# Standard library only: Pillow, numpy, scipy and scikit-image were each
# removed, and PNG-only is deliberate -- see the Line tests.


def load_binary(path: str) -> Mask:
    """Load a PNG as a boolean ink mask (True = black/foreground).

    Greyscale anti-aliasing is thresholded at mid-grey, so softened edges are
    accepted while a dark, connected stroke core remains.

    PNG only, deliberately -- see ``the Line tests``.  A file in any
    other format is refused with a message naming what to do about it rather
    than a bare signature complaint, since "convert it to PNG" is the whole
    of the fix and a lossy format was never a good home for 1px strokes
    anyway.
    """
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:3] == b"\xff\xd8\xff":
        raise ValueError(
            f"{path} is a JPEG; Line drawings must be PNG. JPEG is lossy and "
            "its block quantization erases pixels out of 1px strokes -- "
            "convert with e.g. `sips -s format png in.jpg --out out.png`, "
            "and see render()'s `scale` for drawings that must survive a "
            "lossy pipeline."
        )
    return mask_module.from_grey(png.read_grey(data))


def crop_to_content(mask: Mask, margin: int = 2) -> Mask:
    """Crop ``mask`` to its ink's bounding box.

    ``margin`` pixels of surrounding blank space are kept on every side so
    downstream code (e.g. :func:`find_cursor`'s erosion) still sees genuine
    background immediately around the drawing's own edge, rather than the
    crop boundary itself acting like an artificial wall.

    The bounding box costs one pass over the row list, with a couple of bit
    operations per non-empty row (:meth:`mask.Mask.bounds`), so it is already
    independent of how much blank canvas surrounds the drawing -- a 4600x4600
    canvas holding a small drawing inside a 2000px border measures 0.2ms.
    An earlier version quartered the canvas recursively to get that property
    back from ``numpy.nonzero``, which had to touch every pixel; row bitmasks
    make it fall out for free, and exactly, rather than as a box padded out
    to quadrant boundaries.  Extracted programs are unchanged by that -- same
    tree shape, same opcodes, same geometry relative to the drawing, on all
    five fixtures -- but every coordinate now sits closer to the origin,
    since the crop no longer keeps up to a leaf-size band of blank canvas.
    Nothing downstream reads absolute positions.  Raises :class:`ValueError`
    if the mask is entirely blank.
    """
    bounds = mask.bounds()
    if bounds is None:
        raise ValueError("image contains no ink")
    y0, x0, y1, x1 = bounds
    height, width = mask.shape
    top, bottom = max(0, y0 - margin), min(height, y1 + 1 + margin)
    left, right = max(0, x0 - margin), min(width, x1 + 1 + margin)
    return mask.crop(top, left, bottom - top, right - left)


# Wiki images are 1x, fixtures go to 3x, and every candidate scale is a
# full pass over the mask.
_MAX_SCALE = 16


def detect_scale(mask: Mask) -> int:
    """Find the integer factor a Line drawing was scaled up by.

    Line's own strokes are always 1px wide in the wiki's reference images
    (see ``render.py``'s module docstring); an image scaled up by some
    integer factor keeps every stroke uniformly that many pixels wide.

    Rather than estimating that width from ink area, this tests the property
    :func:`normalize_scale` actually relies on: a ``k``-times upscaled drawing
    is a *pixel replication*, so every ``k``x``k`` block of it (aligned to the
    ink's own top-left corner, since the surrounding blank border is arbitrary
    -- see :func:`crop_to_content`) is uniform, all ink or all blank.  The
    largest such ``k`` is the scale.  This is exact for the nearest-neighbor
    blow-ups the function exists to undo, where the older
    ``ink_pixel_count / skeleton_length`` ratio was a ~5% approximation; the
    two agree on both wiki reference images at 1x-5x.

    A mask with no ink has no scale to detect and returns 1.
    """
    bounds = mask.bounds()
    if bounds is None:
        return 1
    # Anchor to the first ink pixel: crop_to_content's margin is arbitrary.
    top, left, _, _ = bounds
    rows = [row >> left for row in mask.rows[top:]]
    best = 1
    for k in range(2, _MAX_SCALE + 1):
        if _blocks_uniform(rows, k):
            best = k
    return best


def _blocks_uniform(rows: list[int], k: int) -> bool:
    """Whether every ``k`` x ``k`` block of ``rows`` is all ink or all blank.

    Each group of ``k`` rows is collapsed to "any pixel set in this column"
    and "every pixel set in this column" with two row-wide bitwise ops, after
    which a block is uniform exactly when those two agree across it -- so a
    non-uniform block is found without ever looking at an individual pixel.
    """
    for y0 in range(0, len(rows), k):
        group = rows[y0 : y0 + k]
        any_set = 0
        all_set = -1
        for row in group:
            any_set |= row
            all_set &= row
        if len(group) < k:
            # A partial bottom group cannot be a block, so it must be blank.
            if any_set:
                return False
            continue
        block = (1 << k) - 1
        while any_set or all_set:
            if (any_set & block) and (all_set & block) != block:
                return False
            any_set >>= k
            all_set >>= k
    return True


def normalize_scale(mask: Mask) -> Mask:
    """Downscale ``mask`` to 1px-wide strokes if it was rendered larger.

    Detects the drawing's stroke width (:func:`detect_scale`) and, if greater
    than 1, takes one pixel per block of the upscale grid -- confirmed to
    recover the *exact* original pixel-for-pixel mask when reversing a
    nearest-neighbor upscale, which is what every scale this function needs to
    handle in practice looks like (an integer pixel-replication blow-up of a
    1px-wide drawing, not a resampled photograph).  A mask already at native
    scale is returned unchanged.

    The subtlety is *where* the block grid starts.  :func:`crop_to_content`
    only guarantees a bounding box loosely containing the drawing (padded to
    quadtree-leaf boundaries, plus its own margin), so neither the array's
    origin nor its extent is aligned to the stroke width; sampling from index 0
    can therefore slice across blocks instead of through them, and a version of
    this that divided the array up from its corner silently dropped a
    fractional row/column of real content at the far edge -- caught directly on
    the wiki addition example scaled 4x, whose crop width (1054) is not a
    multiple of 4.  Anchoring the grid to the drawing's first ink pixel instead
    sidesteps both ends: the sample always lands inside a block, and there is
    no ragged remainder to lose.
    """
    scale = detect_scale(mask)
    if scale <= 1:
        return mask
    # One pixel per block, anchored to the first ink pixel (see
    # detect_scale); every block is uniform, so which pixel does not matter.
    bounds = mask.bounds()
    if bounds is None:
        raise AssertionError("detect_scale found an inked mask without bounds")
    top, left, _, _ = bounds
    return mask.subsample(scale, top % scale, left % scale)


def _ink_neighbor_count(mask: Mask, y: int, x: int) -> int:
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


def _thick_regions(thick: Mask) -> list[Mask]:
    """Return the 8-connected components of ``thick``, largest first."""
    h, w = thick.shape
    seen = Mask(h, w)
    components: list[list[tuple[int, int]]] = []
    for sy, sx in thick.nonzero():
        if seen[sy, sx]:
            continue
        component = []
        frontier = [(sy, sx)]
        seen[sy, sx] = True
        while frontier:
            y, x = frontier.pop()
            component.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if (
                        0 <= ny < h
                        and 0 <= nx < w
                        and thick[ny, nx]
                        and not seen[ny, nx]
                    ):
                        seen[ny, nx] = True
                        frontier.append((ny, nx))
        components.append(component)
    regions = []
    for component in sorted(components, key=len, reverse=True):
        region = Mask(h, w)
        for y, x in component:
            region[y, x] = True
        regions.append(region)
    return regions


@dataclass
class Cursor:
    """The arrowhead's location, heading, and shape, isolated from a mask."""

    y: float
    x: float
    blob: Mask  # boolean mask, same shape as the source image


# Ink neighbours in the 3x3 that make a pixel arrowhead body rather than
# path: a stroke interior has exactly 2, the triangle's outline 3+.
_BLOB_NEIGHBOR_MIN = 3

# Fraction of its bbox a real arrowhead fills: 0.46-0.61 over all 8
# headings of render.py's own arrowhead (diagonal headings sit low; was
# 0.41-0.55 under Pillow's polygon fill).  Deliberately wide, to reject
# non-triangles: a solid square is 1.0, a crossing-stroke sliver well under
# 0.25.  Multiple blobs inside it are ambiguous.
_FILL_RATIO_RANGE = (0.25, 0.75)


def _fill_ratio(blob: Mask) -> float:
    """Fraction of ``blob``'s own bounding box that is filled."""
    bounds = blob.bounds()
    if bounds is None:
        return 0.0
    top, left, bottom, right = bounds
    return blob.sum() / ((bottom - top + 1) * (right - left + 1))


def _cursor_candidate(mask: Mask, core: Mask) -> Cursor:
    """Grow one eroded component into its full blob and locate its centre."""
    core_pixels = list(core.nonzero())
    cy = sum(y for y, _ in core_pixels) / len(core_pixels)
    cx = sum(x for _, x in core_pixels) / len(core_pixels)

    h, w = mask.shape
    visited = set(core_pixels)
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

    blob = Mask(h, w)
    for y, x in visited:
        blob[y, x] = True
    return Cursor(float(cy), float(cx), blob)


def find_cursor(mask: Mask) -> Cursor:
    """Isolate the whole arrowhead shape via erosion + growth.

    The arrowhead is the only solid (multi-pixel-thick) region in a
    correctly-drawn Line image; every path stroke is 1px wide.  Eroding
    (:func:`_erode`) picks out its thick *interior*, which is enough to locate and
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
    Limiting growth by local pixel density stops naturally at the point the
    silhouette narrows down to the 1px-wide stroke leaving it -- the same
    place a human eye would call "where the arrowhead ends" -- typically
    within a pixel of the triangle's true boundary.

    Every thick component is checked rather than trusting the largest. Exactly
    one arrowhead-shaped blob is required: no plausible candidate raises the
    shape error, while two or more raise an ambiguity error instead of choosing
    by size when the image supplies no basis for that choice.
    """
    thick = mask.erode()
    if not thick.any():
        raise ValueError("no cursor (thick/filled region) found in image")
    candidates = [_cursor_candidate(mask, core) for core in _thick_regions(thick)]
    low, high = _FILL_RATIO_RANGE
    plausible = [c for c in candidates if low <= _fill_ratio(c.blob) <= high]
    if len(plausible) > 1:
        raise ValueError(
            f"ambiguous cursor: found {len(plausible)} arrowhead-shaped regions"
        )
    if plausible:
        return plausible[0]
    ratio = _fill_ratio(candidates[0].blob)
    raise ValueError(
        f"largest thick region does not look like an arrowhead "
        f"(fill ratio {ratio:.2f}, expected {low:.2f}-{high:.2f})"
    )


# The walker lives in lattice.py.  The region-adjacency walker it replaced
# could not tell a merge into a *different* stroke's ink (no background
# pixel between) from a continuation; three local pixel-geometry fixes were
# tried and reverted (see lattice.py's docstring).  The 8-direction
# vertex-star probe resolves it with a cleaner coverage gap on both fixtures.
Stroke = lattice.Stroke
Vertex = lattice.Vertex


def extract_tree(mask: Mask, cursor: Cursor, start_heading: int = 0) -> Stroke:
    """Walk a Line image's full path tree from the cursor.

    ``start_heading`` is a direction index into ``_DIRS`` (default 0 = N,
    "up" -- the heading every wiki example starts from, arrow pointing up
    from the bottom of the drawing).  Delegates to :func:`lattice.walk_tree`
    -- see :mod:`lattice`'s module docstring for why its star-probe walker
    replaced this module's own region-adjacency one.
    """
    stripped = mask & ~cursor.blob
    nearest = min(
        stripped.nonzero(),
        key=lambda p: (p[0] - cursor.y) ** 2 + (p[1] - cursor.x) ** 2,
        default=None,
    )
    if nearest is None:
        raise ValueError("no path pixels found outside the cursor blob")
    start = lattice.find_start(stripped, *nearest, start_heading)
    return lattice.walk_tree(stripped, start, start_heading)


def _direction_runs(vertices: list[Vertex]) -> list[tuple[int, int]]:
    """Convert walked ``vertices`` into ``(direction_index, pixel_length)`` pairs.

    One entry per vertex-to-vertex leg -- each already the maximal run
    :mod:`lattice`'s star-probe walker found between two direction changes
    (see its module docstring), so unlike a dense pixel path this needs no
    run-length merging: :func:`lattice.walk_tree` never emits two consecutive
    vertices sharing a heading.  ``length`` is the Chebyshev distance between
    consecutive vertices (``max(|dy|, |dx|)``), which is exactly the pixel
    count :func:`lattice._walk_segment` advanced by for an on-grid
    8-direction step -- confirmed to match the old dense-path pixel count on
    both wiki fixtures wherever :func:`lattice._snap` did not need to nudge a
    vertex off the pure heading line (see :func:`coverage_gap`'s docstring
    for the cases where it does, and why that is handled at the pixel-redraw
    layer instead of here).
    """
    runs: list[tuple[int, int]] = []
    for i in range(len(vertices) - 1):
        v0, v1 = vertices[i], vertices[i + 1]
        if v0.heading is None:
            raise AssertionError("walker produced a vertex without a heading")
        length = max(abs(v1.y - v0.y), abs(v1.x - v0.x))
        runs.append((v0.heading, length))
    return runs


# Each opcode's kink as (relative_turn, unit_length) pairs (+1/-1 diagonal
# jog, +2/-2 sideways; see the module docstring).  Mirrors render.py's
# `_OPS` exactly -- both measured against Lineanim4/5/6/7/8/10/11.png --
# and additionally checked against `fixtures/addition.png` and
# `multiplication.png`, which caught `>`/`<` and `o` with their diagonal
# and sideways legs in the wrong order.
# Unit length matters, not just sign: `i`'s middle run is 2 units, which is
# what separates it from `>` `>` back to back with no gap (this happens in
# `addition.png`); both start `(+1, -2)`.  `+`/`-` are the only entries
# whose leg length is not fixed -- it is the repeat count (see
# :data:`DEFAULT_UNIT` and render.py's `_op_segments`).
_FIXED_SIGNATURES: dict[tuple[tuple[int, int], ...], str] = {
    ((1, 1), (-2, 1)): ">",
    ((-1, 1), (2, 1)): "<",
    ((1, 1), (-2, 2), (1, 1)): "i",
    ((-2, 1), (1, 2), (-2, 1)): "o",
}
# Longest first, so a greedy scan tries the most specific template.
_FIXED_BY_LENGTH: list[tuple[tuple[tuple[int, int], ...], str]] = sorted(
    _FIXED_SIGNATURES.items(), key=lambda kv: -len(kv[0])
)

# Diagonal-run unit length in the renderer's `_UNIT` grid, doubling as
# `+`/`-`'s repeat count.  `normalize_scale` recovers stroke width, not
# grid unit, so `classify_ops` takes it as a parameter.
DEFAULT_UNIT = 20

# Rounding slack for a run's unit count: wide enough for the +-1px a real
# wiki image shows (addition.png's kinks measure 19px/39px against 20px),
# narrow enough that an off-grid run is a structural difference.
_UNIT_TOLERANCE = 0.15


@dataclass
class OpCall:
    """One classified opcode, plus where its kink sits in the walked stroke.

    ``index`` is the position in the run-length sequence (see
    :func:`_direction_runs`) the kink's *first* non-straight run starts at --
    enough to locate it back in the original ``vertices`` list if a caller
    needs the pixel coordinates, without this module needing to carry them
    around too.
    """

    op: str
    count: int
    index: int


def _round_units(length: int, unit: int) -> int | None:
    """Round a pixel run length to the nearest whole unit count, or ``None``.

    ``None`` signals the length is too far from any whole-unit multiple to
    trust (see :data:`_UNIT_TOLERANCE`) -- distinct from rounding to 0, which
    is a legitimate outcome for a stray noise pixel between two real legs
    (see :func:`classify_ops`).
    """
    units = length / unit
    nearest = round(units)
    if abs(units - nearest) > _UNIT_TOLERANCE:
        return None
    return nearest


def _only_noise_remains(runs: list[tuple[int, int]], start: int, unit: int) -> bool:
    """Whether every run from ``start`` onward is a 0-unit noise pixel.

    Used to tell "this opcode call is genuinely the path's last real thing"
    apart from "there happens to be one more direction-run after it, but
    it's too short (< half a unit) to be anything but noise" -- both look
    the same to a caller checking ``index == len(runs) - 1`` directly (see
    :func:`classify_ops`), confirmed to matter on a real wiki fixture whose
    walked path ends in a single stray pixel just past a merge point.
    """
    return all(_round_units(r_len, unit) == 0 for _, r_len in runs[start:])


def classify_ops(vertices: list[Vertex], unit: int = DEFAULT_UNIT) -> list[OpCall]:
    """Identify which opcodes' kinks appear along a walked stroke's ``vertices``.

    Converts ``vertices`` to direction runs (:func:`_direction_runs`) and scans
    them left to right against a *dynamic* heading (see the ``heading``
    comment below for why it isn't fixed at the path's own start), matching
    ``(relative_turn, unit_length)`` sequences (:func:`_round_units`) against
    :data:`_FIXED_SIGNATURES`, longest template first, or falling back to a
    lone ``+``/``-`` leg (any unit length, since that length is the run's
    repeat count, not a fixed shape -- see ``render.py``'s ``_op_segments``)
    when no fixed template matches at the current position.  A run that
    rounds to 0 units is a stray noise pixel *inside* a kink's real legs
    (confirmed against ``fixtures/addition.png``: a real 1-unit diagonal leg
    there is interrupted by exactly one such stray vertical pixel), not a
    leg of its own, and is skipped.  Anything left over -- a straight run, or
    a turn that starts no valid kink -- is an ordinary corner or
    continuation rather than an opcode, and updates the heading everything
    after it is measured against, rather than raising.

    Matching on ``(turn, units)`` together, not turn sign alone, is load-
    bearing: two ``>`` kinks drawn back to back with no separating straight
    run (confirmed to happen in ``addition.png``) produce the same leading
    ``(+1, -2)`` turn-sign prefix as ``i``'s ``(+1, -2, +1)`` -- only ``i``'s
    middle sideways run being 2 units instead of 1 tells the two apart.

    Never raises: a run that is neither a straight continuation nor a
    recognized kink leg (including one whose length doesn't round
    trustworthily to a whole unit at all, see :func:`_round_units`) is
    indistinguishable, from here, from an ordinary corner the drawing just
    happens to take outside of any opcode -- confirmed necessary, not just
    permissive-by-default, since a branch arm's post-branch corner (see the
    ``heading`` comment above) has exactly this shape.  Callers that want to
    know how much of a path was actually recognized as opcodes can compare
    the returned calls' coverage against the path length themselves.

    The one candidate this function *does* reject outright, after the scan
    above: a match whose final leg is ``path``'s literal last run, with
    nothing following it at all.  A complete opcode always finishes with a
    trailing straight run back to its entry heading (part of the kink's own
    shape, not incidental -- see ``render.py``'s ``_op_segments``), so a walk
    that stops mid-kink was cut off by something else entirely -- confirmed
    against two independent branch arms in
    ``fixtures/multiplication.png`` where the walked path is cut short
    exactly at a merge into another, unrelated stroke (not a real halt),
    each producing exactly one spurious trailing ``+``/``-`` call before
    this check was added.  :mod:`lattice`'s walker does not have that merge
    gap (see its module docstring), but the check is kept regardless: it is
    a property of a genuinely incomplete kink, not of any particular
    walker's failure mode.
    """
    runs = _direction_runs(vertices)
    if not runs:
        return []

    # ``heading`` updates at ordinary corners, as render.py's cursor does
    # between opcodes: `multiplication.png`'s branch arm turns E then N
    # before its first `>`, and relative to E its `>`/`>`/`o` are
    # unrecognizable.  Only a run tested as a kink leg is unit-checked; a
    # run that rounds to 0 (noise) or matches no template updates heading.
    heading = runs[0][0]
    calls: list[OpCall] = []
    ends_at_last_run = False
    i = 0
    while i < len(runs):
        r_idx, r_len = runs[i]
        turn = (r_idx - heading + 4) % 8 - 4
        if turn == 0:
            i += 1
            continue
        units = _round_units(r_len, unit)
        if units == 0:
            # Noise (addition.png has one such pixel inside a diagonal leg).
            i += 1
            continue
        if units is None:
            # Off-unit turn: an ordinary corner, indistinguishable from a
            # malformed kink from here.
            heading = r_idx
            i += 1
            continue

        matched = False
        for signature, op in _FIXED_BY_LENGTH:
            n = len(signature)
            candidate = []
            ok = True
            j = i  # read position, distinct from the template leg count k:
            # A noise run can sit between two legs (addition.png's `i`
            # kinks each have one), so n legs may take more than n runs.
            for _ in range(n):
                while j < len(runs) and _round_units(runs[j][1], unit) == 0:
                    j += 1
                if j >= len(runs):
                    ok = False
                    break
                k_idx, k_len = runs[j]
                k_turn = (k_idx - heading + 4) % 8 - 4
                if k_turn == 0:
                    ok = False
                    break
                k_units = _round_units(k_len, unit)
                if k_units is None:
                    ok = False
                    break
                candidate.append((k_turn, k_units))
                j += 1
            if ok and tuple(candidate) == signature:
                calls.append(OpCall(op, 1, i))
                ends_at_last_run = _only_noise_remains(runs, j, unit)
                i = j
                matched = True
                break
        if matched:
            continue

        if turn in (1, -1):
            calls.append(OpCall("+" if turn == 1 else "-", units, i))
            ends_at_last_run = _only_noise_remains(runs, i + 1, unit)
            i += 1
            continue

        # Ordinary corner or continuation: adopt its direction as heading.
        heading = r_idx
        i += 1

    # A real opcode ends with a straight run back to its entry heading, so
    # a candidate whose last leg is the path's literal last run was a turn
    # cut off entering a merge (two arms of `multiplication.png`, one
    # spurious `-` each).  Only the last call can hit this.
    if calls and ends_at_last_run:
        calls.pop()
    return calls


flatten = lattice.flatten


def count_pivots(stroke: Stroke) -> int:
    """Count the branch pivots in a stroke tree (one per real fork)."""
    count = 1 if stroke.zero is not None or stroke.nonzero is not None else 0
    if stroke.zero is not None:
        count += count_pivots(stroke.zero)
    if stroke.nonzero is not None:
        count += count_pivots(stroke.nonzero)
    return count


def _redraw(vertex_lists: list[list[Vertex]], mask: Mask) -> Mask:
    """Draw every walked vertex-to-vertex leg's real ink onto a blank canvas.

    A leg is redrawn by re-walking ``mask`` pixel by pixel from its start
    vertex along its heading (mirroring :func:`lattice._walk_segment`
    exactly) rather than assuming a straight line the fixed Chebyshev
    distance to the next vertex -- :func:`lattice._snap` can land a vertex a
    pixel off the pure heading line to correct onto a *different* leg's true
    centerline (see its docstring), so the straight-line assumption
    undercounts real ink right at such a corner (confirmed on
    ``fixtures/addition.png``: a pure heading-replay from ``(202, 159)``
    stops one pixel short, at ``(183, 178)``, of the recorded next vertex
    ``(182, 178)``, silently missing that pixel of real ink every time this
    exact bend shape recurs).  Explicitly marking each leg's own endpoint
    vertex too closes that gap: whatever pixel :func:`lattice._snap` chose as
    the true corner is real ink either way, even on the rare step its own
    heading's pixel walk does not reach it.
    """
    canvas = Mask(*mask.shape)
    for vertices in vertex_lists:
        for i in range(len(vertices) - 1):
            v0, v1 = vertices[i], vertices[i + 1]
            if v0.heading is None:
                raise AssertionError("walker produced a vertex without a heading")
            dy, dx = _DIRS[v0.heading]
            py, px = v0.y, v0.x
            canvas[py, px] = True
            while _ink(mask, py + dy, px + dx):
                py, px = py + dy, px + dx
                canvas[py, px] = True
            canvas[v1.y, v1.x] = True
    return canvas


# Deliberate gap between walked pixels and source ink: 2 arrowhead-tip
# corners the blob threshold falls a pixel short of (see find_cursor).
# Exactly 2 on both wiki images regardless of pivot count (1 and 3), since
# lattice.py's vertices mark the true pivot pixel.
_ARROWHEAD_TIP_GAP = 2


def coverage_gap(mask: Mask, cursor: Cursor, stroke: Stroke) -> int:
    """How many source-image ink pixels ``stroke`` leaves unaccounted for.

    Redraws ``stroke``'s walked legs (:func:`_redraw`) and XORs against the
    source (cursor blob excluded, since extraction never attempts to
    reproduce it); a perfect extraction differs only at the deliberate gap
    described in :data:`_ARROWHEAD_TIP_GAP`, so this returns exactly that
    constant for a fully-accounted extraction on real input -- confirmed on
    both wiki fixtures, an improvement over the previous region-adjacency
    walker's gap, which also grew by one pixel per branch pivot (see
    :func:`_redraw`'s docstring for why lattice.py's vertices do not have
    that same per-pivot loss).  A larger value means real ink was never
    walked -- confirmed to happen concretely from JPEG recompression: at
    quality 32 and below, block quantization can erase a pixel or two
    directly out of a 1px-wide stroke, severing it, and the walker then
    silently stops short with no other symptom (see extract()).
    """
    vertex_lists = flatten(stroke)
    redrawn = _redraw(vertex_lists, mask)
    reference = mask & ~cursor.blob
    return (redrawn ^ reference).sum()


def extract_mask(mask: Mask) -> Stroke:
    """Extract a walked program from an in-memory greyscale-derived mask."""
    mask = crop_to_content(mask)
    mask = normalize_scale(mask)
    cursor = find_cursor(mask)
    stroke = extract_tree(mask, cursor)
    gap = coverage_gap(mask, cursor, stroke)
    if gap > _ARROWHEAD_TIP_GAP:
        raise ValueError(
            f"extraction left {gap} source pixels unaccounted for "
            f"(expected at most {_ARROWHEAD_TIP_GAP} for a clean drawing) "
            "-- the image may be corrupted, over-compressed, or otherwise "
            "not a clean drawing"
        )
    return stroke


def extract(path: str) -> Stroke:
    """Load a Line image and walk its full path tree, cursor auto-detected.

    Two normalization passes run before any of the 1px-stroke-assuming
    logic (:func:`find_cursor`, :mod:`lattice`'s star-probe walker) sees the
    mask:

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
    return extract_mask(load_binary(path))


if __name__ == "__main__":
    import sys

    def _leg_pixels(vertices: list[Vertex]) -> int:
        total = 0
        for i in range(len(vertices) - 1):
            v0, v1 = vertices[i], vertices[i + 1]
            total += max(abs(v1.y - v0.y), abs(v1.x - v0.x))
        return total

    def _describe(stroke: Stroke, indent: str = "") -> None:
        ops = [c.op for c in classify_ops(stroke.vertices)]
        n = len(stroke.vertices)
        print(f"{indent}stroke: {n} vertices, end={stroke.end}, ops={ops}")
        if stroke.zero is not None:
            print(f"{indent}  zero ->")
            _describe(stroke.zero, indent + "    ")
        if stroke.nonzero is not None:
            print(f"{indent}  nonzero ->")
            _describe(stroke.nonzero, indent + "    ")

    result = extract(sys.argv[1])
    _describe(result)
    total = sum(_leg_pixels(vs) for vs in flatten(result))
    print(f"total walked: {total} px")
