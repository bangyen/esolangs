"""Fold Streetcode corridors into strips connected by bends."""

from collections.abc import Iterator
from itertools import pairwise
from math import isqrt

from esolangs.generation.grid import grid_width
from esolangs.generation.token_balance import CELL_ASPECT

_WALLS = frozenset("-|+")

# Blank rows between two blocks (a strip with its room band), and clear
# columns each side of a cut.  A car reads walls three cells to a side
# (:func:`_road_mouth`, :func:`_plus_dist`), and a lane's nearest outer wall
# is one or two cells out, so two blank rows put every other block's wall at
# least four rows from any road cell.  Four columns put a room's wall at least
# four from the end column, hence beyond what a bend's road cells can read.
_GAP = 2
_MARGIN = 4


def _streetcode_cuts(rows: list[str]) -> list[bool]:
    """Return where the indexed street may be cut: plain road, no room near."""
    span = len(rows[0])
    kerb = len(rows) - 4
    clear = [
        all(row[col] == " " for row in rows[:kerb])
        and rows[kerb][col] == rows[-1][col] == "-"
        for col in range(span)
    ]
    return [
        _MARGIN <= col <= span - _MARGIN and all(clear[col - _MARGIN : col + _MARGIN])
        for col in range(span)
    ]


def _streetcode_bounds(rows: list[str], target: int, *, east: bool) -> list[int]:
    """Return strip bounds: legal cuts at most ``target`` apart where possible.

    Cutting from the east packs the rooms, which all lie there, into the
    fewest strips (each adds a band); from the west, the fill does.
    """
    span = len(rows[0])
    legal = _streetcode_cuts(rows)

    def cuts(cols: range) -> Iterator[int]:
        return (col for col in cols if legal[span - col if east else col])

    bounds = [0]
    while span - bounds[-1] > target:
        start = bounds[-1]
        within = list(cuts(range(start + 4, start + target + 1)))
        beyond = cuts(range(start + target + 1, span))
        # A cut always remains in range: columns 5 and ``span - 5`` are
        # legal cuts at the street's plain ends, and every caller passes
        # ``target >= 8``, so this pass starts at most ``span - 9`` and
        # the far end's cut lies in the searched range either direction.
        cut = within[-1] if within else next(beyond)
        bounds.append(cut)
    bounds.append(span)
    return [span - bound for bound in reversed(bounds)] if east else bounds


def _streetcode_strips(
    rows: list[str], bounds: list[int]
) -> tuple[dict[tuple[int, int], str], dict[tuple[int, int], tuple[int, int]]]:
    """Snake ``rows`` (a band of rooms over a four-row street) between ``bounds``.

    Odd strips are turned a half turn, which keeps right-hand driving, and
    run back under the one before.  A block is a strip with its room band
    (rooms hang above an even strip's kerb, below an odd one's), trimmed to
    its tallest room; blocks are stacked ``_GAP`` blank rows apart, each
    walled on its own.  A bend is a U of road two cells wide: an inner bar
    closing the gap between the two strips' inner walls, an outer wall from
    one outer wall to the other.  Also returns each strip cell's source cell.
    """
    kerb = len(rows) - 4
    sill = len(rows) - 1
    canvas: dict[tuple[int, int], str] = {}
    origin: dict[tuple[int, int], tuple[int, int]] = {}

    def put(row: int, col: int, char: str) -> None:
        # Walls that meet join through a corner.
        old = canvas.get((row, col))
        if old in _WALLS and char in _WALLS and old != char:
            char = "+"
        canvas[row, col] = char

    def column(col: int, top: int, bottom: int) -> None:
        put(top, col, "+")
        for row in range(top + 1, bottom):
            put(row, col, "|")
        put(bottom, col, "+")

    segments = [[row[a:b] for row in rows] for a, b in pairwise(bounds)]
    firsts = [
        next((r for r in range(kerb) if segment[r].strip()), kerb)
        for segment in segments
    ]
    # Odd blocks are the street turned over: row r is at ``sill - r``.
    top = 0
    start = 0  # the column the strip's first column lies on
    for i, segment in enumerate(segments):
        first = firsts[i]
        height = sill - first + 1
        even = i % 2 == 0
        step = 1 if even else -1
        for row in range(first, sill + 1):
            at_row = top + row - first if even else top + sill - row
            for col, char in enumerate(segment[row]):
                at = at_row, start + step * col
                origin[at] = row, bounds[i] + col
                if char != " ":
                    put(*at, char)
        north = top + kerb - first if even else top
        if i + 1 == len(segments):
            break
        # The far end of this strip is where the next one begins.
        far = start + step * (len(segment[0]) - 1)
        later = top + height + _GAP
        north_next = later if even else later + kerb - firsts[i + 1]
        # Inner bar from this strip's south wall to the next one's north wall;
        # the outer wall from this north wall to the next one's south wall.
        column(far, north + 3, north_next)
        column(far + 3 * step, north, north_next + 3)
        for col in (far + step, far + 2 * step):
            put(north, col, "-")
            put(north_next + 3, col, "-")
        top, start = later, far
    return canvas, origin


def _streetcode_fold(
    flat: str, target: int, *, east: bool
) -> tuple[str, dict[tuple[int, int], tuple[int, int]]]:
    """Snake the indexed street into strips of at most ``target`` columns.

    Also returns each strip cell's flat cell; the bends have none.
    """
    rows = flat.splitlines()
    span = max(map(len, rows))
    rows = [row.ljust(span) for row in rows]
    canvas, origin = _streetcode_strips(
        rows, _streetcode_bounds(rows, target, east=east)
    )
    ymin = min(row for row, _ in canvas)
    xmin = min(col for _, col in canvas)
    height = max(row for row, _ in canvas) - ymin + 1
    width = max(col for _, col in canvas) - xmin + 1
    grid = [[" "] * width for _ in range(height)]
    for (row, col), char in canvas.items():
        grid[row - ymin][col - xmin] = char
    program = "\n".join("".join(row).rstrip() for row in grid)
    return program, {(row - ymin, col - xmin): at for (row, col), at in origin.items()}


def _streetcode_folded(flat: str, *, tall: bool = False) -> str:
    """Return the indexed street folded to about square, east cuts first.

    A strip's block is ``_SILL - _KERB + 1 + _GAP`` rows plain, ``_SILL + 1 +
    _GAP`` with its room band.  East cuts pack the room columns into the
    fewest strips, so the share of strips with a band is the room columns'
    share of the span, and a strip averages ``h`` rows between those.  With
    ``span / target`` strips the height is ``span * h / target``; it squares
    the width when ``target = CELL_ASPECT * span * h / target``.  ``tall``
    is a flat whose rooms stack: the band is each column's own height.
    """
    rows = flat.splitlines()
    span = grid_width(flat)
    kerb = len(rows) - 4
    plain = 4 + _GAP
    if tall:
        padded = [row.ljust(span) for row in rows[:kerb]]
        band = sum(
            kerb - next((r for r, row in enumerate(padded) if row[col] != " "), kerb)
            for col in range(span)
        )
    else:
        west = min(
            (
                col
                for col in range(span)
                if any(row[col : col + 1].strip() for row in rows[:kerb])
            ),
            default=span,
        )
        band = kerb * (span - west)
    target = isqrt(CELL_ASPECT * (plain * span + band))
    return _streetcode_fold(flat, target, east=True)[0]
