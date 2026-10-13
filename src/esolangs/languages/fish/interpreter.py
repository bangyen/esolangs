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

:func:`_advance` is a pure transition over an immutable :data:`_Core`: it
reads the codebox, stack scopes, registers and quote mode and returns the
next core plus the requested output effect, never touching the ports. The
``i`` value arrives already read, and ``x``'s direction already drawn.
:meth:`_Machine.step` is the shell that reads input, draws, applies the
transition and writes the effect; :meth:`snapshot` freezes the core with the
input cursor for cycle detection.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Never, cast

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.memory import format_integer
from esolangs.runtime.randomness import Randomness, draw
from esolangs.runtime.source_hints import syntax_error

type Number = int | float
#: The immutable semantic state: x, y, dx, dy, the codebox mapping, the stack
#: scopes, the registers, the quote mode, the halt flag, and the box bounds.
type _Core = tuple[
    int,
    int,
    int,
    int,
    Mapping[tuple[int, int], int],
    tuple[tuple[Number, ...], ...],
    tuple[Number | None, ...],
    str | None,
    bool,
    int,
    int,
]
#: The hashable snapshot: a core with its codebox flattened and the input
#: cursor appended, which is what the cycle detector stores.
type _State = tuple[object, ...]
#: ``(kind, value)``: ``"char"`` is a codepoint to print, ``"num"`` its text.
type _Effect = tuple[str, object] | None

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


def _fail(hint: str = "check the operand bounds for this instruction") -> Never:
    raise HaltError("something smells fishy...", hint=hint)


def _pop(
    stack: list[Number], hint: str = "push a value before removing the stack top"
) -> Number:
    if not stack:
        _fail(hint)
    return stack.pop()


def _moved(
    x: int, y: int, dx: int, dy: int, width: int, height: int
) -> tuple[int, int]:
    """Return the cell one step along ``(dx, dy)``, wrapping the box."""
    return (x + dx) % width, (y + dy) % height


def _written(
    cells: Mapping[tuple[int, int], int], key: tuple[int, int], value: int
) -> Mapping[tuple[int, int], int]:
    """Return ``cells`` with ``key`` set to ``value``, as a fresh mapping."""
    updated = dict(cells)
    updated[key] = value
    return MappingProxyType(updated)


def _advance(
    state: _Core,
    char_input: int | None = None,
    random_dir: int | None = None,
) -> tuple[_Core, _Effect]:
    """Return the next core and any output effect for the cell at the IP.

    Pure.  ``char_input`` is what ``i`` pushes (``None`` is EOF, so -1);
    ``random_dir`` is the draw ``x`` selects from.  The shell supplies both.
    """
    x, y, dx, dy, cells, packed, register_tuple, quote, halted, width, height = state
    if halted:
        return state, None
    command = _character(cells.get((x, y), 0))
    stacks: list[tuple[Number, ...]] = list(packed)
    registers: list[Number | None] = list(register_tuple)
    stack: list[Number] = list(stacks[-1])
    effect: _Effect = None
    commit = True

    if quote is not None:
        if command == quote:
            quote = None
        else:
            stack.append(ord(command))
    elif command in "'\"":
        quote = command
    elif command in "0123456789abcdef":
        stack.append(int(command, 16))
    elif command in "+-*,%()=":
        right, left = _pop(stack), _pop(stack)
        stack.append(_calculate(command, left, right))
    elif command in "><^v":
        dx, dy = {">": (1, 0), "<": (-1, 0), "^": (0, -1), "v": (0, 1)}[command]
    elif command == "/":
        dx, dy = -dy, -dx
    elif command == "\\":
        dx, dy = dy, dx
    elif command == "|":
        dx = -dx
    elif command == "_":
        dy = -dy
    elif command == "#":
        dx, dy = -dx, -dy
    elif command == "x":
        if random_dir is None:
            _fail("supply a randomness source for this operation")
        dx, dy = _DIRECTIONS[random_dir]
    elif command == "!":
        x, y = _moved(x, y, dx, dy, width, height)
    elif command == "?":
        if _pop(stack) == 0:
            x, y = _moved(x, y, dx, dy, width, height)
    elif command == ".":
        ty, tx = _integer(_pop(stack)), _integer(_pop(stack))
        if tx < 0 or ty < 0:
            _fail()
        x, y = tx, ty
    elif command == ":":
        value = _pop(stack)
        stack.extend((value, value))
    elif command == "~":
        _pop(stack)
    elif command == "$":
        one, two = _pop(stack), _pop(stack)
        stack.extend((one, two))
    elif command == "@":
        one, two, three = _pop(stack), _pop(stack), _pop(stack)
        stack.extend((one, three, two))
    elif command == "}":
        if not stack:
            _fail("push a value before rotating the stack")
        stack.insert(0, stack.pop())
    elif command == "{":
        if not stack:
            _fail("push a value before rotating the stack")
        stack.append(stack.pop(0))
    elif command == "r":
        stack.reverse()
    elif command == "l":
        stack.append(len(stack))
    elif command == "[":
        count = _integer(_pop(stack))
        if count < 0 or count > len(stack):
            _fail("use a stack split count from 0 to the current stack length")
        moved = stack[-count:] if count else []
        if count:
            del stack[-count:]
        stacks[-1] = tuple(stack)
        stacks.append(tuple(moved))
        registers.append(None)
        commit = False
    elif command == "]":
        if len(stacks) == 1:
            stack.clear()
            registers[0] = None
        else:
            popped = stacks.pop()
            registers.pop()
            stacks[-1] = (*stacks[-1], *popped)
            commit = False
    elif command == "&":
        if registers[-1] is None:
            registers[-1] = _pop(stack)
        else:
            stack.append(registers[-1])
            registers[-1] = None
    elif command == "g":
        gy, gx = _integer(_pop(stack)), _integer(_pop(stack))
        stack.append(cells.get((gx, gy), 0))
    elif command == "p":
        py, px, value = (
            _integer(_pop(stack)),
            _integer(_pop(stack)),
            _integer(_pop(stack)),
        )
        cells = _written(cells, (px, py), value)
        if px >= 0:
            width = max(width, px + 1)
        if py >= 0:
            height = max(height, py + 1)
    elif command == "i":
        stack.append(-1 if char_input is None else char_input)
    elif command == "o":
        effect = ("char", _character(_pop(stack)))
    elif command == "n":
        value = _pop(stack)
        if isinstance(value, float):
            if not math.isfinite(value):
                _fail()
            if value.is_integer():
                value = int(value)
        effect = (
            "num",
            format_integer(value) if isinstance(value, int) else str(value),
        )
    elif command == ";":
        return (
            (x, y, dx, dy, cells, packed, register_tuple, quote, True, width, height),
            None,
        )
    elif command not in _NOP:
        _fail("use an instruction documented by esolangs describe --spec Fish")

    if commit:
        stacks[-1] = tuple(stack)
    x, y = _moved(x, y, dx, dy, width, height)
    return (
        (
            x,
            y,
            dx,
            dy,
            cells,
            tuple(stacks),
            tuple(registers),
            quote,
            halted,
            width,
            height,
        ),
        effect,
    )


def _freeze(core: _Core, progress: int) -> _State:
    """Return ``core`` as the hashable snapshot the cycle detector stores."""
    x, y, dx, dy, cells, stacks, registers, quote, halted, width, height = core
    return (
        x,
        y,
        dx,
        dy,
        tuple(sorted(cells.items())),
        stacks,
        registers,
        quote,
        halted,
        width,
        height,
        progress,
    )


def _thaw(state: _State) -> tuple[_Core, int]:
    """Invert :func:`_freeze` for a branching successor."""
    (x, y, dx, dy, cells, stacks, registers, quote, halted, width, height, progress) = (
        state
    )
    return (
        (
            cast(int, x),
            cast(int, y),
            cast(int, dx),
            cast(int, dy),
            MappingProxyType(
                dict(cast(tuple[tuple[tuple[int, int], int], ...], cells))
            ),
            cast(tuple[tuple[Number, ...], ...], stacks),
            cast(tuple[Number | None, ...], registers),
            cast(str | None, quote),
            cast(bool, halted),
            cast(int, width),
            cast(int, height),
        ),
        cast(int, progress),
    )


class _Machine:
    """Fish shell: one immutable :data:`_Core`, rebound per step."""

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
        cells = {
            (x, y): ord(char)
            for y, row in enumerate(code)
            for x, char in enumerate(row)
        }
        self.state: _Core = (
            0,
            0,
            1,
            0,
            MappingProxyType(cells),
            ((),),
            (None,),
            None,
            False,
            width,
            len(code),
        )

    @property
    def halted(self) -> bool:
        return self.state[8]

    @property
    def ip(self) -> tuple[int, ...] | None:
        if self.halted:
            return None
        return (self.state[1], self.state[0], self.state[2], self.state[3])

    @property
    def x(self) -> int:
        return self.state[0]

    @property
    def y(self) -> int:
        return self.state[1]

    @property
    def dx(self) -> int:
        return self.state[2]

    @property
    def dy(self) -> int:
        return self.state[3]

    @property
    def cells(self) -> Mapping[tuple[int, int], int]:
        return self.state[4]

    @property
    def stacks(self) -> list[list[Number]]:
        return [list(stack) for stack in self.state[5]]

    @property
    def registers(self) -> list[Number | None]:
        return list(self.state[6])

    @property
    def quote(self) -> str | None:
        return self.state[7]

    @property
    def width(self) -> int:
        return self.state[9]

    @property
    def height(self) -> int:
        return self.state[10]

    @property
    def stack(self) -> list[object]:
        return list(self.state[5][-1])

    def snapshot(self) -> _State:
        """Return the complete internal state, hashable for cycle detection."""
        return _freeze(self.state, self.io.progress())

    def branching_snapshot(self) -> _State:
        """Return immutable state for exhaustive ``x`` branch search."""
        return self.snapshot()

    def branching_halted(self, state: object) -> bool:
        """Report whether an immutable state has executed ``;``."""
        return bool(cast(_State, state)[8])

    def branching_successors(
        self, state: object, _limit: int
    ) -> tuple[_State, ...] | None:
        """Return every random successor, or ``None`` at input."""
        current = cast(_State, state)
        if self.branching_halted(current):
            return (current,)
        core, progress = _thaw(current)
        command = _character(core[4].get((core[0], core[1]), 0))
        interpreting = core[7] is None
        if interpreting and command == "i":
            return None
        choices = range(4) if interpreting and command == "x" else range(1)
        successors = []
        for choice in choices:
            moved, _effect = _advance(core, random_dir=choice)
            successors.append(_freeze(moved, progress))
        return tuple(successors)

    def step(self) -> None:
        """Execute one instruction, reading, drawing and writing as the shell.

        The transition is :func:`_advance`; this method supplies ``i``'s
        value, ``x``'s draw, and the effect's write.
        """
        if self.halted:
            return
        core = self.state
        command = _character(core[4].get((core[0], core[1]), 0))
        interpreting = core[7] is None
        char_input: int | None = None
        if interpreting and command == "i":
            try:
                char_input = self.io.input_char()
            except EOFError:
                char_input = None
        random_dir = draw(self._rng, 4) if interpreting and command == "x" else None
        core, effect = _advance(core, char_input, random_dir)
        self.state = core
        if effect is not None:
            kind, value = effect
            if kind == "char":
                self.io.print_char(cast(str, value))
            else:
                self.io.print_str(cast(str, value))


def run(code: list[str], io: IO, rng: Randomness | None = None) -> None:
    """Execute a Fish codebox until ``;``."""
    machine = _Machine(code, io, rng)
    drive(machine)


if __name__ == "__main__":
    script_main(run, shape="strip")
