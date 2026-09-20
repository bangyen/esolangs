r"""Interpreter for Befunge.

Befunge is a two-dimensional grid language: the instruction pointer carries a
stack and a heading, wraps at the edges, and ``p`` edits the grid in place.
``,`` and ``.`` print, ``~`` and ``&`` read, and string mode pushes cells as
bytes.  EOF propagates.  The playfield is the specified 80x25 torus; division
truncates toward zero, and a zero divisor reads the result from the user.  A
pop off the empty stack yields 0, ``g`` outside the grid pushes 0, and ``p``
outside is ignored.  ``.`` prints the integer and a trailing space.  An empty
or oversized program raises :class:`ValueError`; a zero divisor with no result
to read raises :class:`~esolangs.exceptions.HaltError`.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import Randomness, draw

#: ``?`` picks one, in the order the shell's draw maps to: right, down, left, up.
_DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))
_WIDTH = 80
_HEIGHT = 25
type _Cursor = tuple[int, int, int, int]
type _Grid = tuple[tuple[str, ...], ...]
type _Stack = tuple[int, ...] | list[int]
type _State = tuple[_Cursor, _Grid, _Stack, bool, bool]
type _Effect = tuple[str, int] | None


def _pop(stack: _Stack) -> tuple[int, _Stack]:
    """Return the top and the rest; an empty stack reads as 0."""
    if not stack:
        return 0, stack
    if isinstance(stack, list):
        return stack.pop(), stack
    return stack[-1], stack[:-1]


def _push(stack: _Stack, *values: int) -> _Stack:
    """Push onto a runtime list or an immutable branching state."""
    if isinstance(stack, list):
        stack.extend(values)
        return stack
    return (*stack, *values)


def _advance(
    state: _State,
    char_input: int | None = None,
    number_input: int | None = None,
    random_dir: int | None = None,
) -> tuple[_State, _Effect]:
    """Return the next state and an output effect, if this cell emits."""
    (col, row, dx, dy), grid, stack, string, done = state
    if done:
        return state, None
    height, width = len(grid), len(grid[0])
    command, effect = grid[row][col], None

    if string and command != '"':
        # String mode consumes every cell, spaces included, until the quote.
        (col, row) = (
            (col + dx) % width,
            (row + dy) % height,
        )
        return (
            ((col, row, dx, dy), grid, _push(stack, ord(command)), True, done),
            None,
        )
    if command == '"':
        string = not string
    elif command.isdigit():
        stack = _push(stack, int(command))
    elif command in "+-*/%":
        a, stack = _pop(stack)
        b, stack = _pop(stack)
        if command == "+":
            stack = _push(stack, b + a)
        elif command == "-":
            stack = _push(stack, b - a)
        elif command == "*":
            stack = _push(stack, b * a)
        elif command == "/":
            if not a:
                if number_input is None:
                    raise HaltError("'/' divides by zero and needs a result")
                stack = (*stack, number_input)
            else:
                quotient = abs(b) // abs(a)
                stack = (*stack, -quotient if (a < 0) != (b < 0) else quotient)
        else:
            if not a:
                if number_input is None:
                    raise HaltError("'%' divides by zero and needs a result")
                stack = (*stack, number_input)
            else:
                quotient = abs(b) // abs(a)
                if (a < 0) != (b < 0):
                    quotient = -quotient
                stack = (*stack, b - quotient * a)
    elif command == "!":
        a, stack = _pop(stack)
        stack = _push(stack, 0 if a else 1)
    elif command == "`":
        a, stack = _pop(stack)
        b, stack = _pop(stack)
        stack = _push(stack, 1 if b > a else 0)
    elif command == ">":
        dx, dy = 1, 0
    elif command == "<":
        dx, dy = -1, 0
    elif command == "^":
        dx, dy = 0, -1
    elif command == "v":
        dx, dy = 0, 1
    elif command == "?":
        if random_dir is None:
            raise HaltError("'?' needs a random draw and none was supplied")
        dx, dy = _DIRECTIONS[random_dir]
    elif command == "_":
        a, stack = _pop(stack)
        dx, dy = (1, 0) if a == 0 else (-1, 0)
    elif command == "|":
        a, stack = _pop(stack)
        dx, dy = (0, 1) if a == 0 else (0, -1)
    elif command == ":":
        a, stack = _pop(stack)
        stack = _push(stack, a, a)
    elif command == "\\":
        a, stack = _pop(stack)
        b, stack = _pop(stack)
        stack = _push(stack, a, b)
    elif command == "$":
        _value, stack = _pop(stack)
    elif command == ".":
        a, stack = _pop(stack)
        effect = ("num", a)
    elif command == ",":
        a, stack = _pop(stack)
        effect = ("char", a & 0xFF)
    elif command == "#":
        col, row = (col + dx) % width, (row + dy) % height
    elif command == "g":
        y, stack = _pop(stack)
        x, stack = _pop(stack)
        in_grid = 0 <= y < height and 0 <= x < width
        stack = _push(stack, ord(grid[y][x]) if in_grid else 0)
    elif command == "p":
        y, stack = _pop(stack)
        x, stack = _pop(stack)
        v, stack = _pop(stack)
        if 0 <= y < height and 0 <= x < width:
            rows = list(grid)
            cols = list(rows[y])
            cols[x] = chr(v & 0xFF)
            rows[y] = tuple(cols)
            grid = tuple(rows)
    elif command == "&":
        if number_input is None:
            raise HaltError("'&' reads a number and there is no input left")
        stack = _push(stack, number_input)
    elif command == "~":
        if char_input is None:
            raise HaltError("'~' reads a character and there is no input left")
        stack = _push(stack, char_input)
    elif command == "@":
        done = True
    col, row = (col + dx) % width, (row + dy) % height
    return (((col, row, dx, dy), grid, stack, string, done), effect)


class _Machine:
    """Protocol shell holding one immutable Befunge state value."""

    #: The first draw is a fact about the program, so a seed makes it repeat.
    reproducible_seed = 0

    def __init__(
        self, code: Sequence[str], io: IO, rng: Randomness | None = None
    ) -> None:
        if not code or not (width := max(map(len, code), default=0)):
            raise ValueError("Befunge program cannot be empty")
        if width > _WIDTH or len(code) > _HEIGHT:
            raise ValueError("Befunge program exceeds its 80x25 playfield")
        rows = [row.ljust(_WIDTH) for row in code]
        rows.extend(" " * _WIDTH for _ in range(_HEIGHT - len(rows)))
        self.grid = tuple(tuple(row) for row in rows)
        self.code, self.io, self._rng = code, io, rng
        self.state: _State = ((0, 0, 1, 0), self.grid, [], False, False)

    @property
    def halted(self) -> bool:
        return self.state[4]

    #: ``ip`` is a cell of the program's own rectangle: a column and a row,
    #: then the heading, so a caller can draw it rather than guess.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...] | None:
        col, row, dx, dy = self.state[0]
        return None if self.halted else (row, col, dx, dy)

    @property
    def memory(self) -> list[int]:
        """Befunge's ``p`` edits the grid, not a separate store."""
        return []

    @property
    def stack(self) -> list[object]:
        return list(self.state[2])

    def snapshot(self) -> tuple[object, ...]:
        cursor, grid, stack, string, done = self.state
        return (*cursor, grid, tuple(stack), string, done, self.io.position())

    def branching_snapshot(self) -> _State:
        """Return the current state as the hang search's starting point."""
        cursor, grid, stack, string, done = self.state
        return cursor, grid, tuple(stack), string, done

    def branching_halted(self, state: object) -> bool:
        """Report whether ``state`` has reached ``@``."""
        return cast(_State, state)[4]

    def branching_successors(
        self, state: object, _limit: int
    ) -> tuple[_State, ...] | None:
        """Return one state per direction ``?`` could take.

        ``None`` for an input cell, whose read cannot be forked.  A
        transition that raises is left to propagate, as it does from
        :meth:`step`: catching it would hide a halting branch.
        """
        current = cast(_State, state)
        if current[4]:
            return (current,)
        col, row, _dx, _dy = current[0]
        command = current[1][row][col]
        if command in "~&":
            return None
        if command == "?":
            return tuple(_advance(current, random_dir=d)[0] for d in range(4))
        return (_advance(current)[0],)

    def step(self) -> None:
        if self.halted:
            return
        (col, row, _dx, _dy), grid, _stack, _string, _done = self.state
        command = grid[row][col]
        char_input = self.io.input_char() if command == "~" else None
        needs_number = command == "&" or (
            command in "/%" and bool(self.state[2]) and self.state[2][-1] == 0
        )
        number_input = self.io.input_num() if needs_number else None
        random_dir = draw(self._rng, 4) if command == "?" else None
        self.state, effect = _advance(self.state, char_input, number_input, random_dir)
        if effect:
            kind, value = effect
            if kind == "char":
                self.io.print_char(chr(value))
            else:
                self.io.print_str(f"{value} ")


def run(code: list[str], io: IO, rng: Randomness | None = None) -> None:
    """Execute a Befunge grid."""
    machine = _Machine(code, io, rng)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read().splitlines(), IO())
