"""Raster row-fit regimes with stack-neutral turns and bounded push blocks."""

from math import isqrt
from typing import NamedTuple

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.raster_lookup import (
    _INITIAL,
    _MULTIPLY,
    _POINTER,
    _POP,
    Pixel,
    _area,
    _candidates,
    _next_colour,
    _Operation,
    _push,
)
from esolangs.generation.raster_lookup.packing import _raster_score, _shape_score, pack
from esolangs.raster import Raster
from esolangs.runtime._validate import check_width
from esolangs.runtime.codels import BLACK

_MIN_COLUMNS = 13  # narrowest width that routes a turn
_MIN_DENSE_COLUMNS = 14  # the left lane must fit the three-codel halt charge


class _Row(NamedTuple):
    first: int
    last: int
    x: int
    y: int
    direction: int


class _Plan(NamedTuple):
    width: int
    height: int
    next_fit: int
    rows: list[_Row]
    compact: bool = False
    dense: bool = False

    def score(self) -> tuple[int, int, int]:
        return _shape_score(self.width, self.height)


def _improves(candidate: tuple[int, int, int], ceiling: tuple[int, int, int]) -> bool:
    """Return whether ``candidate`` scores better without growing the area."""
    return candidate[1] <= ceiling[1] and candidate < ceiling


def _bounded_operations(table: str) -> list[_Operation]:
    """Replace the depth push by doubling; blocks use at most two cells."""
    options = []
    for operations in _candidates(table, _validate_truth_table(table)):
        result = []
        for operation in operations:
            if operation.size > 2:
                result.append(_push(1))
                for _ in range(operation.size.bit_length() - 1):
                    result.extend((_push(2), _Operation(_MULTIPLY)))
            else:
                result.append(operation)
        options.append(result)
    # Keep the halt block away from the preceding vertical turn.
    return [*min(options, key=_area), _push(2), _Operation(_POP)]


def _plan(
    operations: list[_Operation],
    columns: int,
    stop: int,
    *,
    compact: bool = False,
    dense: bool = False,
) -> _Plan:
    """Return the folded shape and first future greedy-fit change."""

    def needed(at: int) -> int:
        # The penultimate block is charged 3 codels so the halt column fits.
        return 3 if at == len(operations) - 2 else operations[at].size

    rows = []
    at, x, y, direction = 0, 2, 1, 1
    widest = 1
    while at < len(operations):
        first, used = at, 0
        room = columns - x - 4 if direction == 1 else x - (7 if dense else 5)
        while at < len(operations):
            if used + needed(at) > room:
                break
            used += operations[at].size
            at += 1
        if at == first:
            raise AssertionError("Raster row has no room for a bounded block")
        rows.append(_Row(first, at, x, y, direction))
        if at == len(operations):
            widest = max(widest, x + direction * used)
            break
        if direction == 1:
            stop = min(stop, x + 4 + used + needed(at))
            x += used + 2
            widest = max(widest, x)
        else:
            x -= used + (3 if compact and not dense else 4)
        direction = -direction
        y += (2 if direction == -1 or dense else 3) if compact else 4
    # At two-row spacing the halt column reconnects to the preceding lane
    # (01101001, width 13 printed repeatedly). Keep the final bend taller.
    if compact and len(rows) > 1 and rows[-2].direction == 1:
        rows[-1] = rows[-1]._replace(y=rows[-1].y + 2)
        y += 2
    elif dense and len(rows) > 1:
        rows[-1] = rows[-1]._replace(y=rows[-1].y + 1)
        y += 1
    width = widest + (2 if len(rows) > 1 else 1)
    return _Plan(width, y + 2, stop, rows, compact, dense)


def _emit(operations: list[_Operation], plan: _Plan) -> Raster:
    rows = [[BLACK] * plan.width for _ in range(plan.height)]

    def put(x: int, y: int, colour: Pixel) -> None:
        if not (0 <= x < plan.width and 0 <= y < plan.height):
            raise AssertionError("Raster fold exceeds its planned image")
        if rows[y][x] != BLACK:
            raise AssertionError("Raster fold overwrites an existing block")
        rows[y][x] = colour

    for x, y in ((0, 0), (0, 1), (1, 1)):
        put(x, y, _INITIAL)
    colour = _next_colour(_INITIAL, _POP)
    x = y = 0

    def block(operation: _Operation, dx: int, dy: int) -> None:
        nonlocal x, y, colour
        for _ in range(operation.size):
            put(x, y, colour)
            x, y = x + dx, y + dy
        colour = _next_colour(colour, operation.change)

    for number, row in enumerate(plan.rows):
        x, y = row.x, row.y
        for operation in operations[row.first : row.last]:
            block(operation, row.direction, 0)
        if number == len(plan.rows) - 1:
            for offset in (-1, 0, 1):
                put(x, y + offset, colour)
            break
        # Horizontal push(3) blocks make left bends two rows high; the final
        # L-shaped block keeps the halt column away from the preceding lane.
        value = 1 if row.direction == 1 else 3
        block(_push(value), row.direction, 0)
        block(_Operation(_POINTER), row.direction, 0)
        if plan.dense and value == 3:
            final = number == len(plan.rows) - 2
            cells = ((0, 0), (-1, 0), (0, 1)) if final else ((0, 0), (-1, 0), (-2, 0))
            for dx, dy in cells:
                put(x + dx, y + dy, colour)
            colour = _next_colour(colour, _push(3).change)
            y += 2 if final else 1
        elif plan.compact and value == 3:
            for dx, dy in ((0, 0), (0, 1), (1, 1)):
                put(x + dx, y + dy, colour)
            colour = _next_colour(colour, _push(3).change)
            x, y = x + 1, y + 2
        else:
            block(_push(value), 0, 1)
        if value == 1 and (not plan.compact or number == len(plan.rows) - 2):
            block(_Operation(_POP), 0, 1)
            block(_push(1), 0, 1)
        block(_Operation(_POINTER), 0, 1)
        following = plan.rows[number + 1]
        if (x, y) != (following.x, following.y):
            raise AssertionError("Raster turn model disagrees with its emitted path")
    return Raster(tuple(tuple(row) for row in rows))


def folded(table: str, columns: int) -> Raster:
    """Return a folded Raster program, with a thirteen-column routing floor."""
    check_width(columns)
    operations = _bounded_operations(table)
    return _emit(
        operations,
        _tight_plan(operations, max(_MIN_COLUMNS, columns), columns + 1),
    )


def _tight_plan(operations: list[_Operation], columns: int, stop: int) -> _Plan:
    """Use two-row bends only when they fit within the compact area ceiling."""
    compact = _plan(operations, columns, stop, compact=True)
    if columns < _MIN_DENSE_COLUMNS:
        return compact
    dense = _plan(operations, columns, stop, compact=True, dense=True)
    selected = compact
    if _improves(dense.score(), compact.score()):
        selected = dense
    return selected._replace(next_fit=min(compact.next_fit, dense.next_fit))


def _balanced_plan(
    operations: list[_Operation], default: Raster, *, compact: bool
) -> _Plan:
    """Balance the strip and all bounded-block row-fit layouts."""
    cells = sum(operation.size for operation in operations)
    pitch = 3 if compact else 4
    target = max(_MIN_COLUMNS, isqrt(pitch * cells - 1) + 7)

    def fit(columns: int, stop: int) -> _Plan:
        return _plan(operations, columns, stop, compact=compact)

    # One row is narrower than its columns, so the strip is its own choice.
    strip = 4 * cells + 64
    selected = min(fit(target, target + 1), fit(strip, strip + 1), key=_Plan.score)
    side = min(selected.score(), _raster_score(default))[0]
    # Past one row, width is at least W-1, so a tie needs W <= side+1.  A
    # row holds at most W cells and is a pixel tall, so W >= cells/side.
    lower = max(_MIN_COLUMNS, cells // side)
    upper = max(target, side + 1)
    while lower <= upper:
        plan = fit(lower, upper + 1)
        if plan.score() < selected.score():
            selected = plan
        lower = plan.next_fit
    return selected


def balance(table: str, default: Raster) -> Raster:
    """Balance folded paths, retaining the old area ceiling."""
    # Seed 20261009, 200 random tables/arity: n=7 area 255101 -> 228867;
    # n=8 441706 -> 322460 codels. Exhaustive n=3: 79068 -> 64572.
    # Two-row bends, seed 20261011, 200 tables/arity: n=8 area 323319 ->
    # 279358 (-13.60%); black codels 212010 -> 165729. n=3: 62663 -> 56465.
    operations = _bounded_operations(table)
    old = _balanced_plan(operations, default, compact=False)
    compact = _balanced_plan(operations, default, compact=True)
    default_score = _raster_score(default)
    old_score = min(old.score(), default_score)
    selected = old
    if _improves(compact.score(), old_score):
        selected = compact
    if default_score > selected.score():
        packed = pack(operations, _emit(operations, selected))
        # Packing minimizes area, not the shape: 00001000's 13x7 plan packs
        # to 14x3, a larger square than the 10x3 default.
        if _raster_score(packed) <= default_score:
            return packed
    return default
