"""Interpreter for Piet: the program is a picture, and colour changes are the commands.

Spec: https://www.dangermouse.net/esoteric/piet.html.  An image is a grid
of codels in 18 colours (six hues, three lightnesses) plus white and black.
Same-coloured neighbours form a block.  Execution starts in the top-left
block and leaves it along the direction pointer (dp: right, down, left,
up), picking the far edge's left or right corner by the codel chooser (cc).
Blocked by black or the image edge, it flips cc, then turns dp, and halts
after eight failed tries.  White is crossed in a straight slide and runs
nothing.  A colour outside the 18 standard ones is treated as white.

Entering a new coloured block runs a command chosen by how far the hue and
lightness stepped, cyclically, from the old block to the new one.
``push`` pushes the size of the block left; ``pointer`` turns dp clockwise
by the popped value and ``switch`` flips cc that many times; ``roll`` pops
a depth and a count and rotates that many of the values beneath.

Commands:
    push: hue +0, lightness +1
    pop: hue +0, lightness +2
    add: hue +1, lightness +0
    subtract: hue +1, lightness +1
    multiply: hue +1, lightness +2
    divide: hue +2, lightness +0
    mod: hue +2, lightness +1
    not: hue +2, lightness +2
    greater: hue +3, lightness +0
    pointer: hue +3, lightness +1
    switch: hue +3, lightness +2
    duplicate: hue +4, lightness +0
    roll: hue +4, lightness +1
    in(number): hue +4, lightness +2
    in(char): hue +5, lightness +0
    out(number): hue +5, lightness +1
    out(char): hue +5, lightness +2

Input/output:
    Input commands share a cursor: character reads preserve newlines;
    numeric reads consume whitespace-delimited integers.  Input commands at
    EOF are ignored.

Decisions:
    * A command that cannot be performed (too few values, division by zero,
      a negative or too-deep roll) leaves the stack untouched; npiet pops a
      failed roll's two values.
    * A roll of depth 0 is not a failure: it pops both and moves nothing.
    * An output char outside Unicode is popped and not printed.
    * Division floors, as the spec's mod does (npiet truncates).
    * A numeric read consumes a token that is not an integer and ignores it;
      npiet's scanf leaves it unread.
"""

from __future__ import annotations

import operator
import re
from collections.abc import Callable
from contextlib import suppress

from esolangs.raster import Raster
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._source import raster_source as load_source
from esolangs.runtime.codels import (
    BLACK,
    COLOURS,
    WHITE,
    exit_step,
    find_block,
    slide,
)
from esolangs.runtime.io import IO
from esolangs.runtime.memory import parse_integer

__all__ = ["load_source", "run"]

supports_scale = True

Pixel = tuple[int, int, int]
Point = tuple[int, int]


_INTEGER = re.compile(r"[+-]?[0-9]+")


def _colour(pixel: Pixel) -> Pixel:
    """Return a standard colour, treating non-standard colours as white."""
    return pixel if pixel in COLOURS or pixel in {WHITE, BLACK} else WHITE


#: ``(current, dp, cc, stack, halted)``: the codel the pointer is in, the
#: direction pointer (0 right, clockwise), the codel chooser (-1 left,
#: 1 right), the stack, and whether the run has ended.  A plain tuple:
#: a NamedTuple's constructor cost 11% of the step rate.
type _State = tuple[Point, int, int, tuple[int, ...], bool]


type _Effect = tuple[str, int] | None

#: The commands that pop two values and push one, ``second op top``.
_BINARY: dict[tuple[int, int], Callable[[int, int], int]] = {
    (1, 0): operator.add,
    (1, 1): operator.sub,
    (1, 2): operator.mul,
    (2, 0): operator.floordiv,
    (2, 1): operator.mod,
    (3, 0): lambda second, top: int(second > top),
}
_DIVISIONS = {(2, 0), (2, 1)}


def _binary(change: tuple[int, int], stack: tuple[int, ...]) -> tuple[int, ...]:
    """Apply a two-value command; too few values or a zero divisor do nothing."""
    if len(stack) < 2 or (change in _DIVISIONS and stack[-1] == 0):
        return stack
    return (*stack[:-2], _BINARY[change](stack[-2], stack[-1]))


def _roll(stack: tuple[int, ...]) -> tuple[int, ...]:
    """Pop a depth and a count; rotate that deep a slice that many times.

    A negative depth, or one past the stack, does nothing.  Depth 0 is a
    valid roll of nothing: both values still pop.
    """
    if len(stack) < 2:
        return stack
    depth, rolls = stack[-2:]
    if not 0 <= depth <= len(stack) - 2:
        return stack
    stack = stack[:-2]
    rolls = rolls % depth if depth else 0
    if not rolls:
        return stack
    return (*stack[:-depth], *stack[-rolls:], *stack[-depth:-rolls])


def _command(
    change: tuple[int, int], size: int, stack: tuple[int, ...]
) -> tuple[tuple[int, ...], int, int, _Effect]:
    """Run the command a ``(hue, lightness)`` change names.

    Return the new stack, the dp turn, the cc flips, and any I/O for the
    shell to perform.  A command that cannot run leaves the stack as it is.
    """
    turn = flips = 0
    effect: _Effect = None
    match change:
        case (0, 1):  # push
            stack = (*stack, size)
        case (0, 2):  # pop
            stack = stack[:-1]
        case (2, 2) if stack:  # not
            stack = (*stack[:-1], int(stack[-1] == 0))
        case (3, 1) if stack:  # pointer
            stack, turn = stack[:-1], stack[-1]
        case (3, 2) if stack:  # switch
            stack, flips = stack[:-1], stack[-1]
        case (4, 0) if stack:  # duplicate
            stack = (*stack, stack[-1])
        case (4, 1):  # roll
            stack = _roll(stack)
        case (4, 2):  # in(number)
            effect = ("read_num", 0)
        case (5, 0):  # in(char)
            effect = ("read_char", 0)
        case (5, 1) | (5, 2) if stack:  # out(number), out(char)
            kind = "write_num" if change == (5, 1) else "write_char"
            stack, effect = stack[:-1], (kind, stack[-1])
        case _ if change in _BINARY:
            stack = _binary(change, stack)
    return stack, turn, flips, effect


def _slid(
    rows: tuple[tuple[Pixel, ...], ...],
    start: Point,
    current: Point,
    dp: int,
    cc: int,
    stack: tuple[int, ...],
) -> _State:
    """Slide from white ``start``; a slide with no exit halts at ``current``."""
    slid = slide(rows, start, dp, cc, _colour)
    if slid is None:
        return current, dp, cc, stack, True
    point, dp, cc = slid
    return point, dp, cc, stack, False


def _advance(
    state: _State, rows: tuple[tuple[Pixel, ...], ...]
) -> tuple[_State, _Effect]:
    """Leave the current block for the next one; return the state and its I/O.

    Leaving onto a colour runs the command its change names; onto white,
    slides across it; with no way out, halts where it is.
    """
    current, dp, cc, stack, halted = state
    if halted:
        return state, None
    colour = _colour(rows[current[1]][current[0]])
    if colour == WHITE:
        return _slid(rows, current, current, dp, cc, stack), None
    block = find_block(rows, current, _colour)
    exit_ = exit_step(rows, block, dp, cc, _colour)
    if exit_ is None:
        return (current, dp, cc, stack, True), None
    target, dp, cc, target_colour = exit_
    if target_colour == WHITE:
        return _slid(rows, target, current, dp, cc, stack), None
    old_hue, old_lightness = COLOURS[colour]
    new_hue, new_lightness = COLOURS[target_colour]
    change = ((new_hue - old_hue) % 6, (new_lightness - old_lightness) % 3)
    stack, turn, flips, effect = _command(change, len(block), stack)
    cc = -cc if flips % 2 else cc
    return (target, (dp + turn) % 4, cc, stack, False), effect


class _Machine:
    """A Piet run: one immutable state rebound after each pure transition."""

    ip_shape = "grid"
    #: An input command at EOF is ignored and the run goes on, so an
    #: underfed program answers another row (``10000000`` fed ``01``: 1).
    eof_is_a_value = True

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
                # Not ``int``: it takes ``1_0`` and non-ASCII digits.
                if _INTEGER.fullmatch(line):
                    return (*stack, parse_integer(line))
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
        elif not 0xD800 <= value <= 0xDFFF:  # A surrogate is no character either.
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
        black = _colour(self.rows[0][0]) == BLACK
        self.state: _State = ((0, 0), 0, -1, (), black)

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
            self.io.progress(),
            self.halted,
            self._program_key,
            self._input_reads,
        )

    def _read_succeeded(self) -> None:
        self._input_reads += 1

    def step(self) -> None:
        state, effect = _advance(self.state, self.rows)
        current, dp, cc, stack, halted = state
        stack = self.perform_io(stack, effect, self.io, self._read_succeeded)
        self.state = (current, dp, cc, stack, halted)


def run(program: Raster, io: IO, *, scale: int | None = None) -> None:
    """Execute a Piet image, detecting its codel scale."""
    machine = _Machine(program, io, scale=scale)
    drive(machine)


if __name__ == "__main__":
    script_main(run, loader=load_source)
