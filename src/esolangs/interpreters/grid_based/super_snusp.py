r"""Interpreter for Super SNUSP.

Super SNUSP is a grid language with a signed sparse tape and value stack.
``\"`` starts rightward; absent a marker, this interpreter enters the bottom
right moving left. EOF propagates. Invalid stack/arithmetic operations raise
:class:`~esolangs.exceptions.HaltError`; an empty program raises
:class:`ValueError`.

The execution model is a pure transition over immutable ``_State``. The shell
alone handles I/O and random draws, then rebinds the returned state.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import Randomness, draw

_DIRECTIONS = ((0, 1), (1, 0), (0, -1), (-1, 0))
_RULD = (3, 0, 1, 2)
_LURD = (1, 2, 3, 0)
type _State = tuple[
    int, int, int, int, tuple[tuple[int, int], ...], tuple[int, ...], bool, bool
]
type _Effect = tuple[str, int] | None


def _floor_root(value: int, degree: int) -> int:
    if degree <= 0 or (value < 0 and degree % 2 == 0):
        raise HaltError
    if value < 0:
        positive = _floor_root(-value, degree)
        return -positive if positive**degree == -value else -positive - 1
    low, high = 0, 1
    while high**degree <= value:
        high *= 2
    while high - low > 1:
        middle = (low + high) // 2
        if middle**degree <= value:
            low = middle
        else:
            high = middle
    return low


def _read(cells: tuple[tuple[int, int], ...], pointer: int) -> int:
    return next((value for index, value in cells if index == pointer), 0)


def _write(
    cells: tuple[tuple[int, int], ...], pointer: int, value: int
) -> tuple[tuple[int, int], ...]:
    updated = dict(cells)
    if value:
        updated[pointer] = value
    else:
        updated.pop(pointer, None)
    return tuple(sorted(updated.items()))


def _top(values: tuple[int, ...]) -> int:
    if not values:
        raise HaltError
    return values[-1]


def _advance(
    state: _State,
    code: Sequence[str],
    char_input: int | None = None,
    number_input: int | None = None,
    random_offset: int | None = None,
) -> tuple[_State, _Effect]:
    """Return the pure next state and an output effect, if this cell emits."""
    row, col, heading, pointer, cells, values, last_digit, done = state
    if done:
        return state, None
    command, value, effect, steps = code[row][col], _read(cells, pointer), None, 1
    if command.isdigit():
        cells = _write(cells, pointer, (10 * value if last_digit else 0) + int(command))
        last_digit = True
    else:
        last_digit = False
        if command == "!":
            steps = 2
        elif command == "'":
            return (row, col, heading, pointer, cells, values, False, True), None
        elif command == "#":
            effect = ("num", value)
        elif command == "$":
            _top(values)
            values = values[:-1]
        elif command == "%":
            divisor = _top(values)
            if not divisor:
                raise HaltError
            rem = abs(value) % abs(divisor)
            cells = _write(cells, pointer, -rem if value < 0 else rem)
        elif command in "&*+-:;[]^|":
            operand = _top(values)
            if command == "&":
                value &= operand
            elif command == "*":
                value *= operand
            elif command == "+":
                value += operand
            elif command == "-":
                value -= operand
            elif command == ":":
                if not operand:
                    raise HaltError
                value //= operand
            elif command == ";":
                value = _floor_root(value, operand)
            elif command == "[":
                if operand < 0:
                    raise HaltError
                value <<= operand
            elif command == "]":
                if operand < 0:
                    raise HaltError
                value >>= operand
            elif command == "^":
                value ^= operand
            else:
                value |= operand
            cells = _write(cells, pointer, value)
        elif command == ",":
            if char_input is None:
                raise HaltError
            cells = _write(cells, pointer, char_input)
        elif command == ".":
            try:
                chr(value)
            except ValueError:
                raise HaltError from None
            effect = ("char", value)
        elif command == "/":
            heading = _RULD[heading]
        elif command == "\\":
            heading = _LURD[heading]
        elif command == "=":
            other = _top(values)
            if random_offset is None:
                raise HaltError
            low, high = sorted((value, other))
            if not 0 <= random_offset <= high - low:
                raise HaltError
            cells = _write(cells, pointer, low + random_offset)
            values = values[:-1]
        elif command == "(":
            cells = _write(cells, pointer, value - 1)
        elif command == ")":
            cells = _write(cells, pointer, value + 1)
        elif command == "<":
            pointer -= 1
        elif command == ">":
            pointer += 1
        elif command == "?":
            steps = 2 if value == 0 else 1
        elif command == "@":
            if number_input is None:
                raise HaltError
            cells = _write(cells, pointer, number_input)
        elif command == "_":
            cells = _write(cells, pointer, -value)
        elif command == "`":
            steps = 2 if value < 0 else 1
        elif command == "{":
            values = (*values, value)
        elif command == "}":
            cells = _write(cells, pointer, _top(values))
        elif command == "~":
            cells = _write(cells, pointer, ~value)
        elif command.isalpha():
            cells = _write(cells, pointer, ord(command))
    d_row, d_col = _DIRECTIONS[heading]
    row += d_row * steps
    col += d_col * steps
    done = not (0 <= row < len(code) and 0 <= col < len(code[0]))
    return (row, col, heading, pointer, cells, values, last_digit, done), effect


class _Machine:
    """Protocol shell holding one immutable Super SNUSP state value."""

    def __init__(
        self, code: Sequence[str], io: IO, rng: Randomness | None = None
    ) -> None:
        if not code or not (width := max(map(len, code), default=0)):
            raise ValueError("Super SNUSP program cannot be empty")
        self.code = tuple(row.ljust(width) for row in code)
        self.io, self._rng = io, rng
        starts = [
            (r, c)
            for r, line in enumerate(self.code)
            for c, char in enumerate(line)
            if char == '"'
        ]
        row, col, heading = (
            (*starts[0], 0) if starts else (len(self.code) - 1, width - 1, 2)
        )
        self.state: _State = (row, col, heading, 0, (), (), False, False)

    @property
    def halted(self) -> bool:
        return self.state[7]

    @property
    def ip(self) -> tuple[int, ...] | None:
        return None if self.halted else self.state[:3]

    @property
    def memory(self) -> list[int]:
        return [value for _, value in self.state[4]]

    @property
    def stack(self) -> list[object]:
        return list(self.state[5])

    def snapshot(self) -> tuple[object, ...]:
        return (*self.state, self.io.position())

    def step(self) -> None:
        if self.halted:
            return
        row, col, _heading, pointer, cells, values, _digit, _done = self.state
        command = self.code[row][col]
        char_input = self.io.input_char() if command == "," else None
        number_input = self.io.input_num() if command == "@" else None
        random_offset = None
        if command == "=" and values:
            low, high = sorted((_read(cells, pointer), values[-1]))
            random_offset = draw(self._rng, high - low + 1)
        self.state, effect = _advance(
            self.state, self.code, char_input, number_input, random_offset
        )
        if effect:
            kind, value = effect
            if kind == "char":
                self.io.print_char(chr(value))
            else:
                self.io.print_num(value)


def run(code: list[str], io: IO, rng: Randomness | None = None) -> None:
    """Execute a Super SNUSP grid."""
    machine = _Machine(code, io, rng)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read().splitlines(), IO())
