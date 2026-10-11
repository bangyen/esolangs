r"""Interpreter for Fish (``><>``), using the current non-threaded language.

The codebox wraps as a rectangle and stores raw Unicode codepoints; counts
and coordinates must be integral. ``p`` may expand positive bounds and use
negative coordinates as storage. An IP that ``.`` sends past the box re-enters
it modulo the box's size; the spec leaves this open, and fish.py instead walks
the empty cells to the edge. Character input returns -1 at EOF. Division
uses Python's true division, matching the specification's floating result.
``o`` needs an integral codepoint. Only a space and an empty cell are no-ops:
a tab, or a control character ``p`` writes, is an invalid instruction. A
string pushes an empty cell (past a short row) as 0, its ``g`` value; fish.py
pushes a space, as it stores spaces as 0.
Invalid instructions, stack underflow, and division by zero raise
:class:`~esolangs.exceptions.HaltError`; an empty program raises
:class:`ValueError`.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Sequence
from typing import cast

from esolangs._drive import drive
from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.memory import format_integer
from esolangs.interpreters.randomness import FirstDraw, Randomness, draw
from esolangs.interpreters.source_hints import syntax_error

type Number = int | float
type _State = tuple[object, ...]

_DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))
_NOP = " \0"


def _integer(value: Number) -> int:
    """Return an integer operand or fail as Fish does on invalid use."""
    if isinstance(value, float) and not value.is_integer():
        raise HaltError("something smells fishy...", hint="use a whole-number operand")
    return int(value)


def _character(value: Number) -> str:
    """Decode a codepoint or raise a Fish runtime error."""
    value = _integer(value)
    if not 0 <= value <= 0x10FFFF:
        raise HaltError("something smells fishy...")
    return chr(value)


def _calculate(command: str, left: Number, right: Number) -> Number:
    """Evaluate arithmetic, rejecting unsupported floating results."""
    try:
        if command == "+":
            result = left + right
        elif command == "-":
            result = left - right
        elif command == "*":
            result = left * right
        elif command in ",%":
            if right == 0:
                raise HaltError(
                    "something smells fishy...", hint="use a nonzero divisor"
                )
            result = left / right if command == "," else left % right
        elif command == "(":
            result = int(left < right)
        elif command == ")":
            result = int(left > right)
        else:
            result = int(left == right)
    except OverflowError:
        raise HaltError("something smells fishy...") from None
    if isinstance(result, float) and not math.isfinite(result):
        raise HaltError("something smells fishy...")
    return result


class _Machine:
    """Mutable Fish codebox, stack scopes, registers, and instruction pointer."""

    reproducible_seed = 0
    ip_shape = "grid"

    def __init__(
        self, code: Sequence[str], io: IO, rng: Randomness | None = None
    ) -> None:
        if not code or not (width := max(map(len, code), default=0)):
            raise syntax_error(
                "Fish program cannot be empty",
                "provide a nonempty grid; ; halts immediately",
            )
        self.code = code
        self.io = io
        self._rng = rng
        self.cells = {
            (x, y): ord(char)
            for y, row in enumerate(code)
            for x, char in enumerate(row)
        }
        self.width, self.height = width, len(code)
        self.x = self.y = 0
        self.dx, self.dy = 1, 0
        self.stacks: list[list[Number]] = [[]]
        self.registers: list[Number | None] = [None]
        self.quote: str | None = None
        self.halted = False

    @property
    def ip(self) -> tuple[int, ...] | None:
        return None if self.halted else (self.y, self.x, self.dx, self.dy)

    @property
    def stack(self) -> list[object]:
        return list(self.stacks[-1])

    def snapshot(self) -> tuple[object, ...]:
        return (
            self.x,
            self.y,
            self.dx,
            self.dy,
            tuple(sorted(self.cells.items())),
            tuple(map(tuple, self.stacks)),
            tuple(self.registers),
            self.quote,
            self.halted,
            self.width,
            self.height,
            self.io.progress(),
        )

    def branching_snapshot(self) -> _State:
        """Return immutable state for exhaustive ``x`` branch search."""
        return self.snapshot()

    def branching_halted(self, state: object) -> bool:
        """Report whether an immutable state has executed ``;``."""
        return bool(cast(_State, state)[8])

    def _restore(self, state: _State) -> None:
        self.x, self.y = cast(int, state[0]), cast(int, state[1])
        self.dx, self.dy = cast(int, state[2]), cast(int, state[3])
        cells, stacks, registers = state[4], state[5], state[6]
        self.quote = cast(str | None, state[7])
        self.halted = cast(bool, state[8])
        self.cells = dict(cast(tuple[tuple[tuple[int, int], int], ...], cells))
        self.width, self.height = cast(int, state[9]), cast(int, state[10])
        packed = cast(tuple[tuple[Number, ...], ...], stacks)
        self.stacks = [list(stack) for stack in packed]
        self.registers = list(cast(tuple[Number | None, ...], registers))

    def branching_successors(
        self, state: object, _limit: int
    ) -> tuple[_State, ...] | None:
        """Return every random successor, or ``None`` at input."""
        current = cast(_State, state)
        if self.branching_halted(current):
            return (current,)
        x, y = cast(int, current[0]), cast(int, current[1])
        frozen_cells = cast(tuple[tuple[tuple[int, int], int], ...], current[4])
        command = _character(dict(frozen_cells).get((x, y), 0))
        interpreting = current[7] is None
        if interpreting and command == "i":
            return None
        choices = range(4) if interpreting and command == "x" else range(1)
        successors = []
        for choice in choices:
            branch = copy.deepcopy(self)
            branch._restore(current)  # noqa: SLF001 - same-class state fork
            branch.io = ScriptedIO("")
            branch._rng = FirstDraw(choice)  # noqa: SLF001 - same-class state fork
            branch.step()
            successors.append((*branch.snapshot()[:-1], current[-1]))
        return tuple(successors)

    def _fail(
        self, hint: str = "check the operand bounds for this instruction"
    ) -> None:
        raise HaltError("something smells fishy...", hint=hint)

    def _pop(self) -> Number:
        if not self.stacks[-1]:
            self._fail("push a value before removing the stack top")
        return self.stacks[-1].pop()

    def _advance(self, count: int = 1) -> None:
        for _ in range(count):
            self.x = (self.x + self.dx) % self.width
            self.y = (self.y + self.dy) % self.height

    def step(self) -> None:
        if self.halted:
            return
        command = _character(self.cells.get((self.x, self.y), 0))
        stack = self.stacks[-1]
        if self.quote is not None:
            if command == self.quote:
                self.quote = None
            else:
                stack.append(ord(command))
            self._advance()
            return
        if command in "'\"":
            self.quote = command
        elif command in "0123456789abcdef":
            stack.append(int(command, 16))
        elif command in "+-*,%()=":
            right, left = self._pop(), self._pop()
            stack.append(_calculate(command, left, right))
        elif command in "><^v":
            self.dx, self.dy = {
                ">": (1, 0),
                "<": (-1, 0),
                "^": (0, -1),
                "v": (0, 1),
            }[command]
        elif command == "/":
            self.dx, self.dy = -self.dy, -self.dx
        elif command == "\\":
            self.dx, self.dy = self.dy, self.dx
        elif command == "|":
            self.dx = -self.dx
        elif command == "_":
            self.dy = -self.dy
        elif command == "#":
            self.dx, self.dy = -self.dx, -self.dy
        elif command == "x":
            self.dx, self.dy = _DIRECTIONS[draw(self._rng, 4)]
        elif command == "!":
            self._advance()
        elif command == "?":
            if self._pop() == 0:
                self._advance()
        elif command == ".":
            y, x = _integer(self._pop()), _integer(self._pop())
            if x < 0 or y < 0:
                self._fail()
            self.x, self.y = x, y
        elif command == ":":
            value = self._pop()
            stack.extend((value, value))
        elif command == "~":
            self._pop()
        elif command == "$":
            one, two = self._pop(), self._pop()
            stack.extend((one, two))
        elif command == "@":
            one, two, three = self._pop(), self._pop(), self._pop()
            stack.extend((one, three, two))
        elif command == "}":
            if not stack:
                self._fail("push a value before rotating the stack")
            stack.insert(0, stack.pop())
        elif command == "{":
            if not stack:
                self._fail("push a value before rotating the stack")
            stack.append(stack.pop(0))
        elif command == "r":
            stack.reverse()
        elif command == "l":
            stack.append(len(stack))
        elif command == "[":
            count = _integer(self._pop())
            if count < 0 or count > len(stack):
                self._fail("use a stack split count from 0 to the current stack length")
            moved = stack[-count:] if count else []
            if count:
                del stack[-count:]
            self.stacks.append(moved)
            self.registers.append(None)
        elif command == "]":
            if len(self.stacks) == 1:
                stack.clear()
                self.registers[0] = None
            else:
                moved = self.stacks.pop()
                self.registers.pop()
                self.stacks[-1].extend(moved)
        elif command == "&":
            if self.registers[-1] is None:
                self.registers[-1] = self._pop()
            else:
                stack.append(self.registers[-1])
                self.registers[-1] = None
        elif command == "g":
            y, x = _integer(self._pop()), _integer(self._pop())
            stack.append(self.cells.get((x, y), 0))
        elif command == "p":
            y, x, value = (
                _integer(self._pop()),
                _integer(self._pop()),
                _integer(self._pop()),
            )
            self.cells[(x, y)] = value
            if x >= 0:
                self.width = max(self.width, x + 1)
            if y >= 0:
                self.height = max(self.height, y + 1)
        elif command == "i":
            try:
                stack.append(self.io.input_char())
            except EOFError:
                stack.append(-1)
        elif command == "o":
            self.io.print_char(_character(self._pop()))
        elif command == "n":
            value = self._pop()
            if isinstance(value, float):
                if not math.isfinite(value):
                    self._fail()
                if value.is_integer():
                    value = int(value)
            self.io.print_str(
                format_integer(value) if isinstance(value, int) else str(value)
            )
        elif command == ";":
            self.halted = True
            return
        elif command not in _NOP:
            self._fail("use an instruction documented by esolangs describe --spec Fish")
        self._advance()


def run(code: list[str], io: IO, rng: Randomness | None = None) -> None:
    """Execute a Fish codebox until ``;``."""
    machine = _Machine(code, io, rng)
    drive(machine)


if __name__ == "__main__":
    script_main(run, shape="strip")
