"""Piet row-fit regimes with stack-neutral turns and bounded push blocks."""

from collections.abc import Callable
from math import isqrt
from typing import NamedTuple

from esolangs._validate import check_width
from esolangs.interpreters.stack_based.piet import BLACK
from esolangs.raster import Raster
from esolangs.tools.helpers import _validate_truth_table

from . import (
    _INITIAL,
    _MULTIPLY,
    _POP,
    Change,
    Pixel,
    _area,
    _candidates,
    _next_colour,
    _Operation,
    _push,
)

_POINTER = (3, 1)
_MIN_COLUMNS = 13  # narrowest width that routes a turn


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

    def score(self) -> tuple[int, int, int]:
        return abs(self.width - self.height), self.width * self.height, self.width


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
    operations: list[_Operation], columns: int, stop: int, *, compact: bool = False
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
        room = columns - x - 4 if direction == 1 else x - 5
        while at < len(operations):
            if used + needed(at) > room:
                break
            used += operations[at].size
            at += 1
        if at == first:
            raise AssertionError("Piet row has no room for a bounded block")
        rows.append(_Row(first, at, x, y, direction))
        if at == len(operations):
            widest = max(widest, x + direction * used)
            break
        if direction == 1:
            stop = min(stop, x + 4 + used + needed(at))
            x += used + 2
            widest = max(widest, x)
        else:
            x -= used + (3 if compact else 4)
        direction = -direction
        y += (2 if direction == -1 else 3) if compact else 4
    # A two-row gap lets the halt column touch the preceding instruction row.
    if compact and len(rows) > 1 and rows[-2].direction == 1:
        rows[-1] = rows[-1]._replace(y=rows[-1].y + 2)
        y += 2
    width = widest + (2 if len(rows) > 1 else 1)
    return _Plan(width, y + 2, stop, rows, compact)


def _emit(
    operations: list[_Operation],
    plan: _Plan,
    *,
    initial: Pixel = _INITIAL,
    next_colour: Callable[[Pixel, Change], Pixel] = _next_colour,
) -> Raster:
    rows = [[BLACK] * plan.width for _ in range(plan.height)]

    def put(x: int, y: int, colour: Pixel) -> None:
        if not (0 <= x < plan.width and 0 <= y < plan.height):
            raise AssertionError("Piet fold exceeds its planned image")
        if rows[y][x] != BLACK:
            raise AssertionError("Piet fold overwrites an existing block")
        rows[y][x] = colour

    for x, y in ((0, 0), (0, 1), (1, 1)):
        put(x, y, initial)
    colour = next_colour(initial, _POP)
    x = y = 0

    def block(operation: _Operation, dx: int, dy: int) -> None:
        nonlocal x, y, colour
        for _ in range(operation.size):
            put(x, y, colour)
            x, y = x + dx, y + dy
        colour = next_colour(colour, operation.change)

    for number, row in enumerate(plan.rows):
        x, y = row.x, row.y
        for operation in operations[row.first : row.last]:
            block(operation, row.direction, 0)
        if number == len(plan.rows) - 1:
            for offset in (-1, 0, 1):
                put(x, y + offset, colour)
            break
        # Compact turns use a two-row right turn and an L-shaped push(3)
        # on the left. Keep the final right turn tall to isolate the halt.
        value = 1 if row.direction == 1 else 3
        block(_push(value), row.direction, 0)
        block(_Operation(_POINTER), row.direction, 0)
        if plan.compact and value == 3:
            for dx, dy in ((0, 0), (0, 1), (1, 1)):
                put(x + dx, y + dy, colour)
            colour = next_colour(colour, _push(3).change)
            x, y = x + 1, y + 2
        else:
            block(_push(value), 0, 1)
        if value == 1 and (not plan.compact or number == len(plan.rows) - 2):
            block(_Operation(_POP), 0, 1)
            block(_push(1), 0, 1)
        block(_Operation(_POINTER), 0, 1)
        following = plan.rows[number + 1]
        if (x, y) != (following.x, following.y):
            raise AssertionError("Piet turn model disagrees with its emitted path")
    return Raster(tuple(tuple(row) for row in rows))


def folded(table: str, columns: int) -> Raster:
    """Return a folded Piet program, with a thirteen-column routing floor."""
    check_width(columns)
    operations = _bounded_operations(table)
    return _emit(
        operations,
        _plan(operations, max(_MIN_COLUMNS, columns), columns + 1, compact=True),
    )


def _balanced_plan(
    operations: list[_Operation], default: Raster, *, compact: bool
) -> _Plan:
    """Balance the strip and all bounded-block row-fit layouts."""
    cells = sum(operation.size for operation in operations)
    pitch = 3 if compact else 4
    target = max(_MIN_COLUMNS, isqrt(pitch * cells - 1) + 7)
    selected = _plan(operations, target, target + 1, compact=compact)
    width, height = len(default.rows[0]), len(default.rows)
    default_score = abs(width - height), width * height, width
    gap = min(selected.score(), default_score)[0]
    # Full rows hold W-10..W cells; width is W-1..W. The old height is
    # 4*rows-1; compact height lies in 2*rows+1..3*rows+1. These quadratic
    # bounds exclude widths that cannot improve the current aspect gap.
    lower = max(_MIN_COLUMNS, (isqrt((gap + 1) ** 2 + 16 * cells) - gap - 1) // 2)
    upper = max(target, (gap + 15 + isqrt((gap - 5) ** 2 + 16 * cells)) // 2 + 2)
    if compact:
        lower = max(_MIN_COLUMNS, (isqrt((gap + 1) ** 2 + 8 * cells) - gap - 1) // 2)
        upper = max(target, (gap + 15 + isqrt((gap - 5) ** 2 + 12 * cells)) // 2 + 2)
    while lower <= upper:
        plan = _plan(operations, lower, upper + 1, compact=compact)
        if plan.score() < selected.score():
            selected = plan
        lower = plan.next_fit
    return selected


def balance(table: str, default: Raster) -> Raster:
    """Balance folded paths, retaining the old area ceiling."""
    # Seed 20261009, 200 random tables/arity: n=7 area 255101 -> 228867;
    # n=8 441706 -> 322460 codels. Exhaustive n=3: 79068 -> 64572.
    operations = _bounded_operations(table)
    old = _balanced_plan(operations, default, compact=False)
    compact = _balanced_plan(operations, default, compact=True)
    default_score = (
        abs(len(default.rows[0]) - len(default.rows)),
        len(default.rows[0]) * len(default.rows),
        len(default.rows[0]),
    )
    old_score = min(old.score(), default_score)
    selected = old
    if compact.score()[1] <= old_score[1] and compact.score() < old_score:
        selected = compact
    if default_score <= selected.score():
        return default
    return _emit(operations, selected)
