"""Piet raster interpreter following https://www.dangermouse.net/esoteric/piet.html.

A program is an image of coloured codels.  The interpreter enters the
top-left block and follows the direction pointer and codel chooser, running
the command named by the hue/lightness change from the block left to the
block entered: hue 0 pushes/pops, 1 adds/subtracts/multiplies, 2
divides/modulos/nots, 3 compares/rotates/switches, 4 duplicates/rolls/reads
a number and 5 reads a char or prints a number/char.  A block with no
colour exit and no white slide ends the run.

A colour outside the 18 standard ones is treated as white. Input commands
share a cursor: character reads preserve newlines; numeric reads consume
whitespace-delimited integers. Input commands at EOF are ignored.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress

from esolangs._drive import drive
from esolangs._source import raster_source as load_source
from esolangs.interpreters.io import IO
from esolangs.raster import Raster

__all__ = ["load_source", "run"]

supports_scale = True

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


type _State = tuple[Point, int, int, tuple[int, ...], bool]
type _Effect = tuple[str, int] | None


def _binary(
    stack: tuple[int, ...], operation: Callable[[int, int], int]
) -> tuple[int, ...]:
    return (*stack[:-2], operation(stack[-2], stack[-1])) if len(stack) >= 2 else stack


def _command(
    change: tuple[int, int], size: int, stack: tuple[int, ...]
) -> tuple[tuple[int, ...], int, int, _Effect]:
    """Return the stack, control changes, and requested I/O effect."""
    lightness = change[1]
    if change == (0, 1):
        stack = (*stack, size)
    elif change == (0, 2):
        stack = stack[:-1]
    elif change == (1, 0):
        stack = _binary(stack, lambda left, right: left + right)
    elif change == (1, 1):
        stack = _binary(stack, lambda left, right: left - right)
    elif change == (1, 2):
        stack = _binary(stack, lambda left, right: left * right)
    elif change in {(2, 0), (2, 1)}:
        if len(stack) >= 2 and stack[-1] != 0:
            left, right = stack[-2:]
            stack = (*stack[:-2], left // right if lightness == 0 else left % right)
    elif change == (2, 2):
        if stack:
            stack = (*stack[:-1], int(stack[-1] == 0))
    elif change == (3, 0):
        stack = _binary(stack, lambda left, right: int(left > right))
    elif change == (3, 1):
        return stack[:-1], stack[-1] if stack else 0, 0, None
    elif change == (3, 2):
        return stack[:-1], 0, stack[-1] if stack else 0, None
    elif change == (4, 0):
        if stack:
            stack = (*stack, stack[-1])
    elif change == (4, 1):
        if len(stack) >= 2:
            depth, rolls = stack[-2:]
            if 0 < depth <= len(stack) - 2:
                stack = stack[:-2]
                rolls %= depth
                if rolls:
                    stack = (*stack[:-depth], *stack[-rolls:], *stack[-depth:-rolls])
    elif change == (4, 2):
        return stack, 0, 0, ("read_num", 0)
    elif change == (5, 0):
        return stack, 0, 0, ("read_char", 0)
    elif change in {(5, 1), (5, 2)} and stack:
        return (
            stack[:-1],
            0,
            0,
            ("write_num" if lightness == 1 else "write_char", stack[-1]),
        )
    return stack, 0, 0, None


def _advance(
    state: _State, rows: tuple[tuple[Pixel, ...], ...]
) -> tuple[_State, _Effect]:
    """Return one pure colour transition or white slide and its I/O request."""
    current, dp, cc, stack, halted = state
    if halted:
        return state, None
    colour = _colour(rows[current[1]][current[0]])
    if colour == WHITE:
        slid = _slide(rows, current, dp, cc)
        return (
            (current, dp, cc, stack, True) if slid is None else (*slid, stack, False)
        ), None
    block = _block(rows, current)
    for attempt in range(8):
        exit_x, exit_y = _exit(block, dp, cc)
        dx, dy = _DIRECTIONS[dp]
        target = exit_x + dx, exit_y + dy
        x, y = target
        if 0 <= x < len(rows[0]) and 0 <= y < len(rows):
            target_colour = _colour(rows[y][x])
            if target_colour == WHITE:
                slid = _slide(rows, target, dp, cc)
                return (
                    (current, dp, cc, stack, True)
                    if slid is None
                    else (*slid, stack, False)
                ), None
            if target_colour != BLACK:
                old_hue, old_lightness = _COLOURS[colour]
                new_hue, new_lightness = _COLOURS[target_colour]
                stack, dp_change, cc_change, effect = _command(
                    ((new_hue - old_hue) % 6, (new_lightness - old_lightness) % 3),
                    len(block),
                    stack,
                )
                return (
                    target,
                    (dp + dp_change) % 4,
                    -cc if cc_change % 2 else cc,
                    stack,
                    False,
                ), effect
        if attempt % 2 == 0:
            cc *= -1
        else:
            dp = (dp + 1) % 4
    return (current, dp, cc, stack, True), None


class _Machine:
    """A Piet run: one immutable state rebound after each pure transition."""

    ip_shape = "grid"

    @staticmethod
    def perform_io(
        stack: tuple[int, ...],
        effect: _Effect,
        io: IO,
        read_succeeded: Callable[[], None] | None = None,
    ) -> tuple[int, ...]:
        """Perform a transition's I/O and return the resulting immutable stack."""
        if effect is None:
            return stack
        action, value = effect
        if action == "read_num":
            try:
                line = io.input_token()
            except EOFError:
                pass
            else:
                if read_succeeded is not None:
                    read_succeeded()
                with suppress(ValueError):
                    return (*stack, int(line))
        elif action == "read_char":
            try:
                value = io.input_char()
            except EOFError:
                pass
            else:
                if read_succeeded is not None:
                    read_succeeded()
                return (*stack, value)
        elif action == "write_num":
            io.print_num(value)
        else:
            with suppress(ValueError):
                io.print_char(chr(value))
        return stack

    def __init__(self, program: Raster, io: IO, *, scale: int | None = None) -> None:
        self.rows = program._normalized(scale)  # noqa: SLF001
        self._program_key = (
            len(self.rows[0]),
            len(self.rows),
            bytes(channel for row in self.rows for pixel in row for channel in pixel),
        )
        self.io = io
        self._input_reads = 0
        self.state: _State = ((0, 0), 0, -1, (), _colour(self.rows[0][0]) == BLACK)

    @property
    def current(self) -> Point:
        return self.state[0]

    @property
    def dp(self) -> int:
        return self.state[1]

    @property
    def cc(self) -> int:
        return self.state[2]

    @property
    def stack(self) -> tuple[int, ...]:
        return self.state[3]

    @property
    def halted(self) -> bool:
        return self.state[4]

    @property
    def ip(self) -> tuple[int, ...] | None:
        return (
            None
            if self.halted
            else (self.current[1], self.current[0], self.dp, self.cc)
        )

    def snapshot(self) -> tuple[object, ...]:
        return (
            self.current,
            self.dp,
            self.cc,
            self.stack,
            self.io.position(),
            self.halted,
            self._program_key,
            self._input_reads,
        )

    def _read_succeeded(self) -> None:
        self._input_reads += 1

    def step(self) -> None:
        state, effect = _advance(self.state, self.rows)
        stack = self.perform_io(state[3], effect, self.io, self._read_succeeded)
        self.state = (*state[:3], stack, state[4])


def run(program: Raster, io: IO, *, scale: int | None = None) -> None:
    """Execute a Piet image, detecting its codel scale."""
    machine = _Machine(program, io, scale=scale)
    drive(machine)
