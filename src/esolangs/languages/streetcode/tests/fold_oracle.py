"""The fold's soundness oracle and the unsound fold it must reject.

``drives_alike`` is the breadth-first drive check that once certified each
candidate fold; the generator no longer calls it, because its folds are sound
by construction.  ``shared_sill_fold`` is the fold it was written for: strips
share a sill with no gap and bends sit two columns from a stalk, 54% unsound
over 2,542 candidates.
"""

from collections.abc import Iterator
from itertools import pairwise

from esolangs.languages.streetcode.generator import _KERB, _SILL, _WALLS
from esolangs.languages.streetcode.interpreter.geometry import (
    _NO_LATCHES,
    _drive,
    _Grid,
    _initial_heading,
    _State,
)


def shared_sill_cuts(rows: list[str]) -> list[bool]:
    """Return where the indexed street may be cut: plain road, no room above.

    Two columns of margin each side keep a bend off a stalk's wall.
    """
    span = len(rows[0])
    clear = [
        all(row[col] == " " for row in rows[:_KERB])
        and rows[_KERB][col] == rows[_SILL][col] == "-"
        for col in range(span)
    ]
    return [2 < col < span - 2 and all(clear[col - 2 : col + 2]) for col in range(span)]


def shared_sill_bounds(rows: list[str], target: int, *, east: bool) -> list[int]:
    """Return strip bounds: legal cuts at most ``target`` apart where possible.

    Cutting from the east packs the rooms, which all lie there, into the
    fewest strips (each adds a band); from the west, the fill does.
    """
    span = len(rows[0])
    legal = shared_sill_cuts(rows)

    def cuts(cols: range) -> Iterator[int]:
        return (col for col in cols if legal[span - col if east else col])

    bounds = [0]
    while span - bounds[-1] > target:
        start = bounds[-1]
        within = list(cuts(range(start + 4, start + target + 1)))
        beyond = cuts(range(start + target + 1, span))
        cut = within[-1] if within else next(beyond, None)
        if cut is None:
            break
        bounds.append(cut)
    bounds.append(span)
    return [span - bound for bound in reversed(bounds)] if east else bounds


def shared_sill_fold(
    flat: str, target: int, *, east: bool
) -> tuple[str, dict[tuple[int, int], tuple[int, int]]]:
    """Snake the indexed street into strips of at most ``target`` columns.

    Each odd strip is turned a half turn, which keeps right-hand driving, and
    runs back under the one before; the pair share a sill.  A cut falls only
    on plain road (:func:`shared_sill_cuts`), so a room wider than a strip
    widens it.  Rooms hang above an even strip's kerb and below an odd one's,
    each in a band of its own.  Also returns each strip cell's flat cell;
    the bends have none.
    """
    rows = flat.splitlines()
    span = max(map(len, rows))
    rows = [row.ljust(span) for row in rows]
    bounds = shared_sill_bounds(rows, target, east=east)

    canvas: dict[tuple[int, int], str] = {}
    origin: dict[tuple[int, int], tuple[int, int]] = {}

    def put(row: int, col: int, char: str) -> None:
        # Walls that meet join through a corner.
        old = canvas.get((row, col))
        if old in _WALLS and char in _WALLS and old != char:
            char = "+"
        canvas[row, col] = char

    def wall(row: int, cols: range, char: str = "-") -> None:
        for col in cols:
            put(row, col, char)

    def column(col: int, top: int, bottom: int) -> None:
        put(top, col, "+")
        for row in range(top + 1, bottom):
            put(row, col, "|")
        put(bottom, col, "+")

    segments = [[row[a:b] for row in rows] for a, b in pairwise(bounds)]
    rooms = [any(row.strip() for row in segment[:_KERB]) for segment in segments]
    kerb = _KERB if rooms[0] else 0
    end = 0  # the column the next strip's joint lies on
    for i, segment in enumerate(segments):
        length = len(segment[0])
        even = i % 2 == 0
        sill = kerb + _SILL - _KERB if even else kerb - 3
        for row, text in enumerate(segment):
            if row < _KERB and not rooms[i]:
                continue  # blank rooms would overlie another strip's lane
            # A half turn maps row r to sill + 8 - r and runs columns west.
            at_row = kerb - _KERB + row if even else sill + _SILL - row
            for col, char in enumerate(text):
                at = at_row, end + col if even else end - col
                origin[at] = row, bounds[i] + col
                if char != " ":
                    put(*at, char)
        if even:
            end += length - 1
            if i + 1 == len(segments):
                break
            # East bend: down past the shared sill, under it.
            put(sill, end, "+")
            canvas[sill, end + 1] = canvas[sill, end + 2] = " "
            wall(kerb, range(end + 1, end + 3))
            wall(sill + 3, range(end + 1, end + 3))
            column(end + 3, kerb, sill + 3)
            kerb = sill + 3
        else:
            end -= length - 1
            if i + 1 == len(segments):
                break
            # West bend: down through both strips' room bands.
            band = rooms[i] + rooms[i + 1]
            below = kerb + 5 * band + (band > 0)
            for row in range(kerb, below + 1):
                canvas[row, end - 1] = canvas[row, end - 2] = " "
            column(end, kerb, below)
            wall(sill, range(end - 2, end))
            wall(below + 3, range(end - 2, end))
            column(end - 3, sill, below + 3)
            kerb = below
    top = min(row for row, _ in canvas)
    left = min(col for _, col in canvas)
    height = max(row for row, _ in canvas) - top + 1
    width = max(col for _, col in canvas) - left + 1
    grid = [[" "] * width for _ in range(height)]
    for (row, col), char in canvas.items():
        grid[row - top][col - left] = char
    program = "\n".join("".join(row).rstrip() for row in grid)
    return program, {(row - top, col - left): at for (row, col), at in origin.items()}


BITS = ((0, 0), (0, 1), (1, 0), (1, 1))


def car(rows: list[str]) -> tuple[_Grid, _State]:
    """Return the street's grid and the car's first state."""
    grid = _Grid(rows)
    start = next((r, row.index("C")) for r, row in enumerate(rows) if "C" in row)
    return grid, _State(*start, _initial_heading(grid, start), _NO_LATCHES)


def drives_alike(
    flat: str, fold: str, origin: dict[tuple[int, int], tuple[int, int]]
) -> bool:
    """Whether the fold's car makes the flat car's every move, bends aside.

    Steering reads the tape only as two zero tests, so pairing the states
    reached under all four answers is exhaustive: when each step lands on
    the strip cell of the flat car's landing, and a bend passes the car
    through whatever the tape holds, both run the same ops on any input.
    A bend corner can line up with another strip's ``+`` and read as a
    junction (a crossing mouth at n=7, first input only), so it is needed.
    """
    flat_grid, flat_car = car(flat.splitlines())
    fold_grid, fold_car = car(fold.splitlines())
    if origin.get((fold_car.row, fold_car.col)) != (flat_car.row, flat_car.col):
        return False
    seen = {(flat_car, fold_car)}
    pending = [(flat_car, fold_car)]
    while pending:
        flat_state, fold_state = pending.pop()
        for bits in BITS:
            want = _drive(flat_grid, flat_state, *bits)
            got = _drive(fold_grid, fold_state, *bits)
            # A bend is at most a few dozen cells; its steering ignores bits.
            for _ in range(64):
                if not isinstance(got, _State) or (got.row, got.col) in origin:
                    break
                moves = {_drive(fold_grid, got, *other) for other in BITS}
                if len(moves) > 1:
                    return False
                (got,) = moves
            if not isinstance(want, _State) or not isinstance(got, _State):
                if want != got:
                    return False
            elif origin.get((got.row, got.col)) != (want.row, want.col):
                return False
            elif (want, got) not in seen:
                seen.add((want, got))
                pending.append((want, got))
    return True
