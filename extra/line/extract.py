r"""Extract a Line program from a rendered PNG."""

from __future__ import annotations

from dataclasses import dataclass

import lattice
import mask as mask_module
import png
from lattice import _DIRS, _ink
from mask import Mask

# This module runs on the.
# scikit-image were each.
# see ``docs/line_tooling.md``.


def load_binary(path: str) -> Mask:
    r"""Load a PNG as a boolean ink mask (True = black/foreground)."""
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
    r"""Crop ``mask`` to its ink's bounding box."""
    bounds = mask.bounds()
    if bounds is None:
        raise ValueError("image contains no ink")
    y0, x0, y1, x1 = bounds
    height, width = mask.shape
    top, bottom = max(0, y0 - margin), min(height, y1 + 1 + margin)
    left, right = max(0, x0 - margin), min(width, x1 + 1 + margin)
    return mask.crop(top, left, bottom - top, right - left)


# No Line drawing this reads is.
# (the wiki's own reference.
# every candidate scale costs a.
# well short of anything a real.
_MAX_SCALE = 16


def detect_scale(mask: Mask) -> int:
    r"""Find the integer factor a Line drawing was scaled up by."""
    bounds = mask.bounds()
    if bounds is None:
        return 1
    # Anchor to the ink itself:.
    # margin, so the array's own.
    # but the drawing's first ink.
    top, left, _, _ = bounds
    rows = [row >> left for row in mask.rows[top:]]
    best = 1
    for k in range(2, _MAX_SCALE + 1):
        if _blocks_uniform(rows, k):
            best = k
    return best


def _blocks_uniform(rows: list[int], k: int) -> bool:
    r"""Whether every ``k`` x ``k`` block of ``rows`` is all ink or all."""
    for y0 in range(0, len(rows), k):
        group = rows[y0 : y0 + k]
        any_set = 0
        all_set = -1
        for row in group:
            any_set |= row
            all_set &= row
        if len(group) < k:
            # A partial group at the bottom.
            # nothing in it may be ink.
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
    r"""Downscale ``mask`` to 1px-wide strokes if it was rendered larger."""
    scale = detect_scale(mask)
    if scale <= 1:
        return mask
    # Sample one pixel per block of.
    # the drawing's own first ink.
    # border crop_to_content leaves.
    # subsampling from index 0 can.
    # Every block is uniform --.
    # because they all are -- so.
    # matter, only that the sample.
    bounds = mask.bounds()
    assert bounds is not None  # detect_scale returned > 1, so.
    top, left, _, _ = bounds
    return mask.subsample(scale, top % scale, left % scale)


def _ink_neighbor_count(mask: Mask, y: int, x: int) -> int:
    r"""How many of (y, x)'s 8 neighbors are ink."""
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


def _largest_thick_region(thick: Mask) -> Mask:
    r"""Find the biggest 8-connected component of ``thick``, as a mask."""
    h, w = thick.shape
    seen = Mask(h, w)
    best: list[tuple[int, int]] = []
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
        if len(component) > len(best):
            best = component
    core = Mask(h, w)
    for y, x in best:
        core[y, x] = True
    return core


@dataclass
class Cursor:
    r"""The arrowhead's location, heading, and shape, isolated from a mask."""

    y: float
    x: float
    blob: Mask  # boolean mask, same shape as.


# A pixel is "blob-like" (part.
# stroke) if it has this many.
# stroke's interior pixels have.
# the triangle's outline and.
_BLOB_NEIGHBOR_MIN = 3

# Fraction of its own bounding.
# rendering render.py's own.
# depending on rotation (a.
# relative to the triangle it.
# 0.41-0.55 when the triangle.
# rasterizes it itself, which.
# unchanged, and was already.
# wide of that measured range.
# triangular at all (a solid.
# a shallow angle either erode.
# thin sliver well under 0.25),.
# arrowhead-shaped candidates,.
# to disambiguate (see.
_FILL_RATIO_RANGE = (0.25, 0.75)


def _fill_ratio(blob: Mask) -> float:
    r"""Fraction of ``blob``'s own bounding box that is filled."""
    bounds = blob.bounds()
    if bounds is None:
        return 0.0
    top, left, bottom, right = bounds
    return blob.sum() / ((bottom - top + 1) * (right - left + 1))


def find_cursor(mask: Mask) -> Cursor:
    r"""Isolate the whole arrowhead shape via erosion + growth."""
    thick = mask.erode()
    if not thick.any():
        raise ValueError("no cursor (thick/filled region) found in image")
    core = _largest_thick_region(thick)
    core_pixels = list(core.nonzero())
    cy = sum(y for y, _ in core_pixels) / len(core_pixels)
    cx = sum(x for _, x in core_pixels) / len(core_pixels)

    h, w = mask.shape
    visited = set(core.nonzero())
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

    ratio = _fill_ratio(blob)
    low, high = _FILL_RATIO_RANGE
    if not low <= ratio <= high:
        raise ValueError(
            f"largest thick region does not look like an arrowhead "
            f"(fill ratio {ratio:.2f}, expected {low:.2f}-{high:.2f})"
        )
    return Cursor(float(cy), float(cx), blob)


# Stroke/Vertex and the.
# its module docstring): the.
# flood-filling the background.
# found via 4-connected-region.
# a merge where one stroke's.
# already-drawn stroke's ink.
# pixel-adjacency walk cannot.
# Three attempts at a local.
# reverted (see lattice.py's.
# lattice.py resolves it from.
# vertex-star probe instead,.
# cleaner coverage-gap result.
# (see coverage_gap's docstring.
Stroke = lattice.Stroke
Vertex = lattice.Vertex


def extract_tree(mask: Mask, cursor: Cursor, start_heading: int = 0) -> Stroke:
    r"""Walk a Line image's full path tree from the cursor."""
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
    r"""Convert walked ``vertices`` into ``(direction_index,."""
    runs: list[tuple[int, int]] = []
    for i in range(len(vertices) - 1):
        v0, v1 = vertices[i], vertices[i + 1]
        assert v0.heading is not None
        length = max(abs(v1.y - v0.y), abs(v1.x - v0.x))
        runs.append((v0.heading, length))
    return runs


# Every opcode's kink, as the.
# it presents between its.
# heading convention (+1/-1 a.
# heading in effect where the.
# relative to that heading) --.
# Lineanim4/5/6/7/8/10/11.png.
# mirrors exactly since both.
# images) *and* against the.
# programs.
# caught two leg-order mistakes.
# didn't surface (``>``/``<``.
# diagonal and sideways legs in.
# .
# The unit length matters here,.
# sideways run is 2 units, not.
# from ``>`` immediately.
# straight run at all --.
# ``addition.png`` (two ``>``.
# between them) -- both start.
# matching on sign alone is.
# are the only entries whose.
# instead the run's repeat.
# reference and.
_FIXED_SIGNATURES: dict[tuple[tuple[int, int], ...], str] = {
    ((1, 1), (-2, 1)): ">",
    ((-1, 1), (2, 1)): "<",
    ((1, 1), (-2, 2), (1, 1)): "i",
    ((-2, 1), (1, 2), (-2, 1)): "o",
}
# Longest signature first, so a.
# match the most specific.
# shorter one that happens to.
_FIXED_BY_LENGTH: list[tuple[tuple[tuple[int, int], ...], str]] = sorted(
    _FIXED_SIGNATURES.items(), key=lambda kv: -len(kv[0])
)

# Diagonal-run unit length (in.
# doubles as `+`/`-`'s repeat.
# increments/decrements is.
# `_FIXED_SIGNATURES`).
# a given image was rendered at.
# width*, not grid unit size --.
# rather than assuming.
DEFAULT_UNIT = 20

# How close a run's pixel.
# accepted rather than raising.
# a hand-drawn or anti-aliased.
# (confirmed: addition.png's.
# consistent 1px short),.
# probably a real structural.
_UNIT_TOLERANCE = 0.15


@dataclass
class OpCall:
    r"""One classified opcode, plus where its kink sits in the walked."""

    op: str
    count: int
    index: int


def _round_units(length: int, unit: int) -> int | None:
    r"""Round a pixel run length to the nearest whole unit count, or."""
    units = length / unit
    nearest = round(units)
    if abs(units - nearest) > _UNIT_TOLERANCE:
        return None
    return nearest


def _only_noise_remains(runs: list[tuple[int, int]], start: int, unit: int) -> bool:
    r"""Whether every run from ``start`` onward is a 0-unit noise pixel."""
    return all(_round_units(r_len, unit) == 0 for _, r_len in runs[start:])


def classify_ops(vertices: list[Vertex], unit: int = DEFAULT_UNIT) -> list[OpCall]:
    r"""Identify which opcodes' kinks appear along a walked stroke's."""
    runs = _direction_runs(vertices)
    if not runs:
        return []

    # ``heading`` is *not* fixed.
    # the path just changing.
    # branch arm continuing along.
    # opcode -- updates it going.
    # cursor heading does between.
    # always restores.
    # guarantee *between*.
    # against.
    # then immediately turns again.
    # -- treating the whole path as.
    # that arm's `>`/`>`/`o` kinks.
    # relative to N, not E.
    # .
    # A straight run's (or.
    # only a run actually being.
    # stretch's length is arbitrary.
    # cursor to its first kink, has.
    # all).
    # when it rounds to 0 units.
    # template matches starting.
    # match is never itself a.
    # necessarily relative to the.
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
            # Stray noise pixel(s).
            # a real 1-unit diagonal leg.
            # such pixel) -- not a real.
            # heading change either.
            i += 1
            continue
        if units is None:
            # Not a whole unit count, but.
            # update, not an error -- a.
            # the same as an ordinary.
            heading = r_idx
            i += 1
            continue

        matched = False
        for signature, op in _FIXED_BY_LENGTH:
            n = len(signature)
            candidate = []
            ok = True
            j = i  # read position, distinct from.
            # a stray noise run (see the.
            # sit *between* two of a kink's.
            # kink starts, so consuming n.
            # more than n runs (confirmed.
            # whose ``i`` kinks each have.
            # between their two diagonal.
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

        # Not a recognized kink leg (or.
        # ordinary corner or.
        # direction as the heading.
        heading = r_idx
        i += 1

    # A real opcode always.
    # its entry heading -- that.
    # render.py's.
    # candidate whose final leg is.
    # nothing after it at all, was.
    # taken right where the path.
    # stroke (confirmed against two.
    # ``fixtures/multiplication.png`.
    # to end in a merge rather than.
    # spurious ``-`` each).
    # since every earlier call is.
    # path.
    if calls and ends_at_last_run:
        calls.pop()
    return calls


flatten = lattice.flatten


def count_pivots(stroke: Stroke) -> int:
    r"""Count the branch pivots in a stroke tree (one per real fork)."""
    count = 1 if stroke.zero is not None or stroke.nonzero is not None else 0
    if stroke.zero is not None:
        count += count_pivots(stroke.zero)
    if stroke.nonzero is not None:
        count += count_pivots(stroke.nonzero)
    return count


def _redraw(vertex_lists: list[list[Vertex]], mask: Mask) -> Mask:
    r"""Draw every walked vertex-to-vertex leg's real ink onto a blank."""
    canvas = Mask(*mask.shape)
    for vertices in vertex_lists:
        for i in range(len(vertices) - 1):
            v0, v1 = vertices[i], vertices[i + 1]
            assert v0.heading is not None
            dy, dx = _DIRS[v0.heading]
            py, px = v0.y, v0.x
            canvas[py, px] = True
            while _ink(mask, py + dy, px + dx):
                py, px = py + dy, px + dx
                canvas[py, px] = True
            canvas[v1.y, v1.x] = True
    return canvas


# The deliberate, non-bug gap.
# source image's ink: 2.
# threshold falls a pixel short.
# of the program's size or.
# adjacency walker, no.
# mark the true pivot pixel.
# step short of the branch (see.
# 2 on both wiki reference.
# 3 for multiplication).
_ARROWHEAD_TIP_GAP = 2


def coverage_gap(mask: Mask, cursor: Cursor, stroke: Stroke) -> int:
    r"""How many source-image ink pixels ``stroke`` leaves unaccounted for."""
    vertex_lists = flatten(stroke)
    redrawn = _redraw(vertex_lists, mask)
    reference = mask & ~cursor.blob
    return (redrawn ^ reference).sum()


def extract(path: str) -> Stroke:
    r"""Load a Line image and walk its full path tree, cursor auto-detected."""
    mask = load_binary(path)
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
