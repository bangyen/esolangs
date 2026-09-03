r"""Interpreter for Super SNUSP.

Super SNUSP is a SNUSP grid with an unbounded signed tape and stack.  The
wiki's opcode table is the specification of record.  Its ``\"`` marker starts
the instruction pointer moving right; without one the table names the bottom
right cell but not a direction, so this interpreter enters that cell moving
left (the inward-facing choice).  Programs halt when they leave the padded
rectangular grid or reach ``'``.

The table distinguishes operations "by stack top" from ``$`` DROP and says
``=`` uses a "stack pop".  Accordingly, every ordinary stack operation reads
without removing the top, while DROP and RAND are the two consuming cases.
An empty stack, division by zero, an invalid root, or a negative shift is an
invalid runtime operation and raises :class:`~esolangs.exceptions.HaltError`.
Both input opcodes propagate :class:`EOFError` when their input is exhausted;
``@`` also propagates :class:`ValueError` for a non-integer line.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import Randomness, draw

# East, south, west, north: the ordering makes the two SNUSP mirror maps
# compact tables indexed by a heading, while still keeping the grid in the
# package-wide (row, column) coordinate convention.
_DIRECTIONS = ((0, 1), (1, 0), (0, -1), (-1, 0))
_RULD = (3, 0, 1, 2)  # /: E->N, S->W, W->S, N->E
_LURD = (1, 2, 3, 0)  # \\: E->S, S->E, W->N, N->W


# Position, heading, tape pointer, sparse signed tape, stack, digit-literal
# continuation flag, and halt flag.  The grid and IO stay outside: source is
# immutable, while effects belong to _Machine.step.
type _State = tuple[
    int,
    int,
    int,
    int,
    tuple[tuple[int, int], ...],
    tuple[int, ...],
    bool,
    bool,
]


def _floor_root(value: int, degree: int) -> int:
    """Return the real ``degree``th root rounded toward negative infinity."""
    if degree <= 0 or (value < 0 and degree % 2 == 0):
        raise HaltError
    if value < 0:
        # floor(-root(abs(value))) is -ceil(root(abs(value))).
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


class _Machine:
    """A step-capable Super SNUSP run.

    Source is padded once, then every step executes the cell under the IP and
    advances once (or twice for a SKIP).  The sparse tape admits both pointer
    directions without an artificial left edge; zero cells are omitted so a
    snapshot records logical state rather than allocation history.
    """

    def __init__(
        self, code: Sequence[str], io: IO, rng: Randomness | None = None
    ) -> None:
        if not code:
            raise ValueError("Super SNUSP program cannot be empty")
        width = max(map(len, code), default=0)
        if not width:
            raise ValueError("Super SNUSP program cannot be empty")
        self.code = tuple(row.ljust(width) for row in code)
        self.height = len(self.code)
        self.width = width
        self.io = io
        self._rng = rng

        starts = [
            (row, col)
            for row, line in enumerate(self.code)
            for col, char in enumerate(line)
            if char == '"'
        ]
        if starts:
            self.row, self.col = starts[0]
            self.heading = 0  # the examples enter from the start marker's right.
        else:
            self.row, self.col = self.height - 1, self.width - 1
            self.heading = 2  # unspecified by the table; enter the grid inward.
        self.pointer = 0
        self.cells: dict[int, int] = {}
        self.values: list[int] = []
        self.last_was_digit = False
        self._done = False

    @property
    def halted(self) -> bool:
        """Whether the pointer reached END or left the grid."""
        return self._done

    @property
    def ip(self) -> tuple[int, ...] | None:
        """The current grid position and heading, or None after halting."""
        return None if self._done else (self.row, self.col, self.heading)

    @property
    def memory(self) -> list[int]:
        """Non-zero tape values in pointer order (the pointer is exposed in ip)."""
        return [value for _, value in sorted(self.cells.items())]

    @property
    def stack(self) -> list[object]:
        """The live value stack, bottom first."""
        return list(self.values)

    def snapshot(self) -> tuple[object, ...]:
        """Return every mutable deterministic state, including input progress."""
        return (
            self.row,
            self.col,
            self.heading,
            self.pointer,
            tuple(sorted(self.cells.items())),
            tuple(self.values),
            self.last_was_digit,
            self._done,
            self.io.position(),
        )

    def _cell(self) -> int:
        return self.cells.get(self.pointer, 0)

    def _set_cell(self, value: int) -> None:
        if value:
            self.cells[self.pointer] = value
        else:
            self.cells.pop(self.pointer, None)

    def _top(self) -> int:
        if not self.values:
            raise HaltError
        return self.values[-1]

    def _pop(self) -> int:
        if not self.values:
            raise HaltError
        return self.values.pop()

    def _advance(self, steps: int = 1) -> None:
        """Move ``steps`` cells in the current heading, stopping off-grid."""
        d_row, d_col = _DIRECTIONS[self.heading]
        self.row += d_row * steps
        self.col += d_col * steps
        if not (0 <= self.row < self.height and 0 <= self.col < self.width):
            self._done = True

    def step(self) -> None:
        """Execute one opcode and move the instruction pointer.

        I/O and RAND live here, at the machine shell.  Everything else only
        updates the machine state, which keeps the port boundary explicit for
        the interpreter-conventions sweep.
        """
        if self._done:
            return
        command = self.code[self.row][self.col]
        value = self._cell()
        if command.isdigit():
            self._set_cell((10 * value if self.last_was_digit else 0) + int(command))
            self.last_was_digit = True
            self._advance()
            return

        self.last_was_digit = False
        steps = 1
        if command == "!":
            steps = 2
        elif command == '"' or command == " ":
            pass
        elif command == "'":
            self._done = True
            return
        elif command == "#":
            self.io.print_num(value)
        elif command == "$":
            self._pop()
        elif command == "%":
            divisor = self._top()
            if not divisor:
                raise HaltError
            remainder = abs(value) % abs(divisor)
            self._set_cell(-remainder if value < 0 else remainder)
        elif command in "&*+-:;[]^|":
            operand = self._top()
            if command == "&":
                self._set_cell(value & operand)
            elif command == "*":
                self._set_cell(value * operand)
            elif command == "+":
                self._set_cell(value + operand)
            elif command == "-":
                self._set_cell(value - operand)
            elif command == ":":
                if not operand:
                    raise HaltError
                self._set_cell(value // operand)
            elif command == ";":
                self._set_cell(_floor_root(value, operand))
            elif command == "[":
                if operand < 0:
                    raise HaltError
                self._set_cell(value << operand)
            elif command == "]":
                if operand < 0:
                    raise HaltError
                self._set_cell(value >> operand)
            elif command == "^":
                self._set_cell(value ^ operand)
            elif command == "|":
                self._set_cell(value | operand)
        elif command == ",":
            self._set_cell(self.io.input_char())
        elif command == ".":
            try:
                self.io.print_char(chr(value))
            except ValueError:
                raise HaltError from None
        elif command == "/":
            self.heading = _RULD[self.heading]
        elif command == "\\":
            self.heading = _LURD[self.heading]
        elif command == "=":
            other = self._pop()
            low, high = sorted((value, other))
            self._set_cell(low + draw(self._rng, high - low + 1))
        elif command == "(":
            self._set_cell(value - 1)
        elif command == ")":
            self._set_cell(value + 1)
        elif command == "<":
            self.pointer -= 1
        elif command == ">":
            self.pointer += 1
        elif command == "?":
            steps = 2 if value == 0 else 1
        elif command == "@":
            self._set_cell(self.io.input_num())
        elif command == "_":
            self._set_cell(-value)
        elif command == "`":
            steps = 2 if value < 0 else 1
        elif command == "{":
            self.values.append(value)
        elif command == "}":
            self._set_cell(self._top())
        elif command == "~":
            self._set_cell(~value)
        elif command.isalpha():
            self._set_cell(ord(command))
        self._advance(steps)


def run(code: list[str], io: IO, rng: Randomness | None = None) -> None:
    """Execute a Super SNUSP grid."""
    machine = _Machine(code, io, rng)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read().splitlines(), IO())
