"""Piet raster interpreter following https://www.dangermouse.net/esoteric/piet.html."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress

from esolangs.interpreters.io import ScriptedIO
from esolangs.raster import Raster

Pixel = tuple[int, int, int]
Point = tuple[int, int]

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# (hue, lightness), in the cycles defined by the Piet specification.
_COLOURS: dict[Pixel, tuple[int, int]] = {
    (255, 192, 192): (0, 0),
    (255, 255, 192): (1, 0),
    (192, 255, 192): (2, 0),
    (192, 255, 255): (3, 0),
    (192, 192, 255): (4, 0),
    (255, 192, 255): (5, 0),
    (255, 0, 0): (0, 1),
    (255, 255, 0): (1, 1),
    (0, 255, 0): (2, 1),
    (0, 255, 255): (3, 1),
    (0, 0, 255): (4, 1),
    (255, 0, 255): (5, 1),
    (192, 0, 0): (0, 2),
    (192, 192, 0): (1, 2),
    (0, 192, 0): (2, 2),
    (0, 192, 192): (3, 2),
    (0, 0, 192): (4, 2),
    (192, 0, 192): (5, 2),
}

# right, down, left, up
_DIRECTIONS: tuple[Point, ...] = ((1, 0), (0, 1), (-1, 0), (0, -1))


def _colour(pixel: Pixel) -> Pixel:
    """Return a standard colour, treating non-standard colours as white."""
    return pixel if pixel in _COLOURS or pixel in {WHITE, BLACK} else WHITE


def _block(rows: tuple[tuple[Pixel, ...], ...], start: Point) -> set[Point]:
    """Return the four-connected colour block containing ``start``."""
    width, height = len(rows[0]), len(rows)
    wanted = _colour(rows[start[1]][start[0]])
    found = {start}
    pending = [start]
    while pending:
        x, y = pending.pop()
        for dx, dy in _DIRECTIONS:
            point = x + dx, y + dy
            px, py = point
            if (
                0 <= px < width
                and 0 <= py < height
                and point not in found
                and _colour(rows[py][px]) == wanted
            ):
                found.add(point)
                pending.append(point)
    return found


def _exit(block: set[Point], dp: int, cc: int) -> Point:
    """Choose the block exit codel for the direction pointer and chooser."""
    dx, dy = _DIRECTIONS[dp]
    edge = max(x * dx + y * dy for x, y in block)
    candidates = [point for point in block if point[0] * dx + point[1] * dy == edge]
    # Image y grows downward: left of travel is (dy, -dx).
    lx, ly = -cc * dy, cc * dx
    return max(candidates, key=lambda point: point[0] * lx + point[1] * ly)


def _slide(
    rows: tuple[tuple[Pixel, ...], ...], start: Point, dp: int, cc: int
) -> tuple[Point, int, int] | None:
    """Slide from a white codel until colour or a repeated white state."""
    width, height = len(rows[0]), len(rows)
    point = start
    seen: set[tuple[Point, int]] = set()
    while True:
        state = point, dp
        if state in seen:
            return None
        seen.add(state)
        dx, dy = _DIRECTIONS[dp]
        target = point[0] + dx, point[1] + dy
        x, y = target
        if 0 <= x < width and 0 <= y < height:
            colour = _colour(rows[y][x])
            if colour == WHITE:
                point = target
                continue
            if colour != BLACK:
                return target, dp, cc
        cc *= -1
        dp = (dp + 1) % 4


def _binary(stack: list[int], operation: Callable[[int, int], int]) -> None:
    if len(stack) < 2:
        return
    right = stack.pop()
    left = stack.pop()
    stack.append(operation(left, right))


def _command(
    change: tuple[int, int], size: int, stack: list[int], io: ScriptedIO
) -> tuple[int, int]:
    """Execute one colour transition, returning DP and CC changes."""
    hue, lightness = change
    if (hue, lightness) == (0, 1):
        stack.append(size)
    elif (hue, lightness) == (0, 2):
        if stack:
            stack.pop()
    elif (hue, lightness) == (1, 0):
        _binary(stack, lambda left, right: left + right)
    elif (hue, lightness) == (1, 1):
        _binary(stack, lambda left, right: left - right)
    elif (hue, lightness) == (1, 2):
        _binary(stack, lambda left, right: left * right)
    elif (hue, lightness) in {(2, 0), (2, 1)}:
        if len(stack) >= 2 and stack[-1] != 0:
            right = stack.pop()
            left = stack.pop()
            stack.append(left // right if lightness == 0 else left % right)
    elif (hue, lightness) == (2, 2):
        if stack:
            stack[-1] = int(stack[-1] == 0)
    elif (hue, lightness) == (3, 0):
        _binary(stack, lambda left, right: int(left > right))
    elif (hue, lightness) == (3, 1):
        return (stack.pop() if stack else 0), 0
    elif (hue, lightness) == (3, 2):
        return 0, (stack.pop() if stack else 0)
    elif (hue, lightness) == (4, 0):
        if stack:
            stack.append(stack[-1])
    elif (hue, lightness) == (4, 1):
        if len(stack) >= 2:
            depth, rolls = stack[-2:]
            if 0 < depth <= len(stack) - 2:
                del stack[-2:]
                rolls %= depth
                if rolls:
                    stack[-depth:] = stack[-rolls:] + stack[-depth:-rolls]
    elif (hue, lightness) == (4, 2):
        with suppress(EOFError, ValueError):
            stack.append(io.input_num())
    elif (hue, lightness) == (5, 0):
        with suppress(EOFError):
            stack.append(io.input_char())
    elif (hue, lightness) == (5, 1):
        if stack:
            io.print_num(stack.pop())
    elif (hue, lightness) == (5, 2) and stack:
        value = stack.pop()
        with suppress(ValueError):
            io.print_char(chr(value))
    return 0, 0


def run(program: Raster, io: ScriptedIO) -> None:
    """Execute a Piet image, with one pixel per codel."""
    rows = program.rows
    current = (0, 0)
    dp, cc = 0, -1
    stack: list[int] = []
    colour = _colour(rows[0][0])
    if colour == BLACK:
        return
    if colour == WHITE:
        slid = _slide(rows, current, dp, cc)
        if slid is None:
            return
        current, dp, cc = slid

    while True:
        colour = _colour(rows[current[1]][current[0]])
        block = _block(rows, current)
        moved = False
        for attempt in range(8):
            exit_x, exit_y = _exit(block, dp, cc)
            dx, dy = _DIRECTIONS[dp]
            target = exit_x + dx, exit_y + dy
            x, y = target
            if 0 <= x < len(rows[0]) and 0 <= y < len(rows):
                target_colour = _colour(rows[y][x])
                if target_colour == WHITE:
                    slid = _slide(rows, target, dp, cc)
                    if slid is None:
                        return
                    current, dp, cc = slid
                    moved = True
                    break
                if target_colour != BLACK:
                    old_hue, old_lightness = _COLOURS[colour]
                    new_hue, new_lightness = _COLOURS[target_colour]
                    dp_change, cc_change = _command(
                        ((new_hue - old_hue) % 6, (new_lightness - old_lightness) % 3),
                        len(block),
                        stack,
                        io,
                    )
                    dp = (dp + dp_change) % 4
                    if cc_change % 2:
                        cc *= -1
                    current = target
                    moved = True
                    break
            if attempt % 2 == 0:
                cc *= -1
            else:
                dp = (dp + 1) % 4
        if not moved:
            return


def generate(truth_table: str) -> Raster:
    """Return a Piet raster computing ``truth_table``."""
    from .piet_boolean import generate as _generate

    return _generate(truth_table)
