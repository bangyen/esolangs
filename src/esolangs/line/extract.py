"""Extract a Line program from a rendered PNG.

Counterpart to :mod:`render`; every segment is one of 8 directions.
This module loads and normalizes an image to a 1px-stroke mask
(:func:`load_binary`, :func:`crop_to_content`, :func:`normalize_scale`),
finds the arrowhead (:func:`find_cursor`), classifies each walked
stroke's kinks (:func:`classify_ops`) and checks the walk covered the
ink (:func:`coverage_gap`).  The walk itself is :mod:`lattice`'s
star-probe, which replaced this module's region-adjacency walker (see
its docstring): a 4-way crossing is not a local per-pixel question.
"""

from __future__ import annotations

from dataclasses import dataclass

from esolangs.raster import png

from . import lattice
from . import mask as mask_module
from .lattice import _DIRS, _ink
from .mask import Mask

# Standard library only: Pillow, numpy, scipy and scikit-image were each
# removed, and PNG-only is deliberate -- see the Line tests.


def load_binary(path: str) -> Mask:
    """Load a PNG as a boolean ink mask (True = black/foreground).

    Thresholded at mid-grey.  PNG only; another format is refused with a
    message saying to convert it.
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
    try:
        grey = png.read_grey(data)
    except Exception as exc:
        # The same decode failures ``Raster.from_png`` wraps; here they used
        # to escape as a bare ``zlib.error``/``struct.error``.
        raise ValueError(f"cannot read {path}: {exc}") from exc
    return mask_module.from_grey(grey)


def crop_to_content(mask: Mask, margin: int = 2) -> Mask:
    """Crop ``mask`` to its ink's bounding box.

    ``margin`` blank pixels stay on every side so :func:`find_cursor`'s
    erosion sees real background.  One pass over row bitmasks
    (:meth:`mask.Mask.bounds`): a 4600x4600 canvas with a 2000px border
    measures 0.2ms, exact rather than quadrant-padded, and nothing downstream
    reads absolute positions.  Raises :class:`ValueError` on a blank mask.
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

    A ``k``-times upscale is a pixel replication, so every ``k``x``k`` block
    aligned to the ink's top-left is uniform; the largest such ``k`` is the
    scale.  Exact, where the ink/skeleton ratio was ~5% off; the two agree on
    both wiki images at 1x-5x.  No ink returns 1.
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

    Each group of ``k`` rows collapses to "any set" and "all set" per column
    with two row-wide ops; uniform iff those agree.
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

    One pixel per block of the :func:`detect_scale` grid, recovering the
    exact original for a nearest-neighbour upscale.  The grid is anchored to
    the first ink pixel: the crop's origin is not aligned to the stroke
    width, and dividing from the corner dropped a fractional column at the
    far edge (the addition example at 4x has crop width 1054).
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

    A stroke interior has exactly 2, a fork a third.
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

    The arrowhead is the only multi-pixel-thick region.  :func:`_erode` finds
    its interior (the largest, so a stray artifact is not mistaken), but the
    1px outline and tips would be left behind (a 13-pixel stub once read as
    a branch), so ``blob`` grows outward admitting a pixel only while it is
    itself blob-like (``_BLOB_NEIGHBOR_MIN``): a fixed radius left outline or
    ate the path, and a flood fill swallowed the drawing since the tip
    touches the path.  Exactly one arrowhead-shaped blob is required: none
    raises the shape error, two or more the ambiguity error.
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

    ``start_heading`` indexes ``_DIRS`` (0 = N, every wiki example).
    Delegates to :func:`lattice.walk_tree`.
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

    One per leg, already maximal (:func:`lattice.walk_tree` never emits two
    consecutive vertices sharing a heading); ``length`` is the Chebyshev
    distance, the pixel count :func:`lattice._walk_segment` advanced
    (matches the old dense count except where :func:`lattice._snap` nudged
    a vertex; see :func:`coverage_gap`).
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

    ``index`` is the run the kink's first non-straight leg starts at.
    """

    op: str
    count: int
    index: int


def _round_units(length: int, unit: int) -> int | None:
    """Round a pixel run length to the nearest whole unit count, or ``None``.

    ``None`` is too far from a multiple to trust (:data:`_UNIT_TOLERANCE`);
    0 is a legitimate stray noise pixel.
    """
    units = length / unit
    nearest = round(units)
    if abs(units - nearest) > _UNIT_TOLERANCE:
        return None
    return nearest


def _only_noise_remains(runs: list[tuple[int, int]], start: int, unit: int) -> bool:
    """Whether every run from ``start`` onward is a 0-unit noise pixel.

    Tells a genuine last opcode from one followed only by noise, which
    ``index == len(runs) - 1`` cannot (a fixture ends in one stray pixel).
    """
    return all(_round_units(r_len, unit) == 0 for _, r_len in runs[start:])


def classify_ops(vertices: list[Vertex], unit: int = DEFAULT_UNIT) -> list[OpCall]:
    """Identify which opcodes' kinks appear along a walked stroke's ``vertices``.

    Scans :func:`_direction_runs` against a dynamic heading, matching
    ``(relative_turn, unit_length)`` against :data:`_FIXED_SIGNATURES`
    longest first, or a lone ``+``/``-`` leg of any length (its repeat
    count).  A 0-unit run is a noise pixel inside a kink (``addition.png``
    has one) and is skipped; anything else unmatched is an ordinary corner
    and updates the heading rather than raising -- a branch arm's post-branch
    corner has exactly that shape.  Matching on units matters: two ``>``
    back to back share ``i``'s ``(+1, -2)`` prefix.  One rejection: a match
    whose final leg is the path's literal last run, since a complete opcode
    ends with a straight run back to its heading (two ``multiplication.png``
    arms cut off at a merge each gave a spurious ``+``/``-``); kept though
    :mod:`lattice` has no merge gap, as a property of an incomplete kink.
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


def _redraw(vertex_lists: list[list[Vertex]], mask: Mask) -> Mask:
    """Draw every walked vertex-to-vertex leg's real ink onto a blank canvas.

    Re-walks ``mask`` pixel by pixel along each heading (as
    :func:`lattice._walk_segment`) rather than assuming a straight line:
    :func:`lattice._snap` can land a vertex a pixel off, and a pure replay
    from ``(202, 159)`` in ``addition.png`` stops at ``(183, 178)``, one
    short of ``(182, 178)``.  Each leg's endpoint vertex is marked too.
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

    XOR of :func:`_redraw` against the source, cursor blob excluded; a
    perfect extraction returns exactly :data:`_ARROWHEAD_TIP_GAP` on both
    fixtures (the old walker's gap also grew per pivot).  Larger means ink
    was never walked: JPEG at quality 32 and below severs a 1px stroke and
    the walker stops short with no other symptom.
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

    :func:`crop_to_content` and :func:`normalize_scale` run first: at 2x and
    up the "3+ neighbours is arrowhead body" rule matches every stroke pixel
    and cursor isolation swallows the drawing.  The tree is checked with
    :func:`coverage_gap` and :class:`ValueError` raised on unwalked ink: a
    JPEG-recompressed wiki image otherwise walks to completion with 85% of
    the drawing unreached.  :func:`extract_tree` gives the best-effort tree.
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
