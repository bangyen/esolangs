"""Piet row-fit regimes with stack-neutral turns and bounded push blocks."""

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
    Pixel,
    _next_colour,
    _Operation,
    _operations,
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

    def score(self) -> tuple[int, int, int]:
        return abs(self.width - self.height), self.width * self.height, self.width


def _bounded_operations(table: str) -> list[_Operation]:
    """Replace the depth push by doubling; blocks use at most two cells."""
    operations = _operations(table, _validate_truth_table(table))
    result = []
    for operation in operations:
        if operation.size > 2:
            result.append(_push(1))
            for _ in range(operation.size.bit_length() - 1):
                result.extend((_push(2), _Operation(_MULTIPLY)))
        else:
            result.append(operation)
    # Keep the halt block away from the preceding vertical turn.
    result.extend((_push(2), _Operation(_POP)))
    return result


def _plan(operations: list[_Operation], columns: int, stop: int) -> _Plan:
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
            x -= used + 4
        direction = -direction
        y += 4
    width = widest + (2 if len(rows) > 1 else 1)
    return _Plan(width, y + 2, stop, rows)


def _emit(operations: list[_Operation], plan: _Plan) -> Raster:
    rows = [[BLACK] * plan.width for _ in range(plan.height)]

    def put(x: int, y: int, colour: Pixel) -> None:
        if not (0 <= x < plan.width and 0 <= y < plan.height):
            raise AssertionError("Piet fold exceeds its planned image")
        if rows[y][x] != BLACK:
            raise AssertionError("Piet fold overwrites an existing block")
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
        # Turn down with value 1 (right edge) or 3 (left edge); the down-left
        # turn needs the extra pop+push(1) to flip the chooser.
        value = 1 if row.direction == 1 else 3
        block(_push(value), row.direction, 0)
        block(_Operation(_POINTER), row.direction, 0)
        block(_push(value), 0, 1)
        if value == 1:
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
    return _emit(operations, _plan(operations, max(_MIN_COLUMNS, columns), columns + 1))


def balance(table: str, default: Raster) -> Raster:
    """Balance the strip and all bounded-block row-fit layouts."""
    operations = _bounded_operations(table)
    cells = sum(operation.size for operation in operations)
    target = max(_MIN_COLUMNS, isqrt(4 * cells - 1) + 7)
    selected = _plan(operations, target, target + 1)
    width, height = len(default.rows[0]), len(default.rows)
    default_score = abs(width - height), width * height, width
    gap = min(selected.score(), default_score)[0]
    # Every full row holds W-10..W cells; height is 4*rows-1 and width W-1..W.
    # Outside these quadratic bounds no layout can improve the current gap.
    lower = max(_MIN_COLUMNS, (isqrt((gap + 1) ** 2 + 16 * cells) - gap - 1) // 2)
    upper = max(target, (gap + 15 + isqrt((gap - 5) ** 2 + 16 * cells)) // 2 + 2)
    while lower <= upper:
        plan = _plan(operations, lower, upper + 1)
        if plan.score() < selected.score():
            selected = plan
        lower = plan.next_fit
    if default_score <= selected.score():
        return default
    return _emit(operations, selected)
