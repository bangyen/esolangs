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
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
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


def _nonzero(value: Number) -> Number:
    """Return a nonzero operand or fail as Fish does on a zero divisor."""
    if value == 0:
        raise HaltError("something smells fishy...", hint="use a nonzero divisor")
    return value


def _divide(left: Number, right: Number) -> Number:
    """Divide, rejecting a zero divisor as Fish does."""
    return left / _nonzero(right)


def _modulo(left: Number, right: Number) -> Number:
    """Take the remainder, rejecting a zero divisor as Fish does."""
    return left % _nonzero(right)


#: Dyadic operators by command character; the nested table replaces the
#: per-operator chain that used to live inside :func:`_calculate`.
_OPERATORS: dict[str, Callable[[Number, Number], Number]] = {
    "+": lambda left, right: left + right,
    "-": lambda left, right: left - right,
    "*": lambda left, right: left * right,
    ",": _divide,
    "%": _modulo,
    "(": lambda left, right: int(left < right),
    ")": lambda left, right: int(left > right),
    "=": lambda left, right: int(left == right),
}


def _calculate(command: str, left: Number, right: Number) -> Number:
    """Evaluate arithmetic, rejecting unsupported floating results."""
    try:
        result = _OPERATORS[command](left, right)
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


@dataclass(slots=True)
class _Step:
    """Mutable scratch state for one :func:`_advance` transition.

    Handlers mutate these fields directly; :meth:`freeze` commits the
    stack, moves the IP, and returns the immutable next core and effect.
    """

    x: int
    y: int
    dx: int
    dy: int
    cells: Mapping[tuple[int, int], int]
    stacks: list[tuple[Number, ...]]
    registers: list[Number | None]
    quote: str | None
    width: int
    height: int
    char_input: int | None
    random_dir: int | None
    stack: list[Number] = field(init=False)
    effect: _Effect = None
    halted: bool = False
    commit: bool = True
    move: bool = True

    def __post_init__(self) -> None:
        self.stack = list(self.stacks[-1])

    def freeze(self) -> tuple[_Core, _Effect]:
        """Return the next core and output effect for this step."""
        if self.commit:
            self.stacks[-1] = tuple(self.stack)
        if self.move:
            self.x, self.y = _moved(
                self.x, self.y, self.dx, self.dy, self.width, self.height
            )
        core: _Core = (
            self.x,
            self.y,
            self.dx,
            self.dy,
            self.cells,
            tuple(self.stacks),
            tuple(self.registers),
            self.quote,
            self.halted,
            self.width,
            self.height,
        )
        return core, self.effect


#: A command handler: mutates the step's scratch state, returning nothing.
_Handler = Callable[[_Step, str], None]


def _string_step(step: _Step, command: str) -> bool:
    """Consume ``command`` as string-mode input.

    Return True when the step is fully handled: opening or closing the
    quote, or pushing the character's codepoint while quoted.
    """
    if step.quote is None:
        if command not in "'\"":
            return False
        step.quote = command
        return True
    if command == step.quote:
        step.quote = None
    else:
        step.stack.append(ord(command))
    return True


_ARROWS: dict[str, tuple[int, int]] = {
    ">": (1, 0),
    "<": (-1, 0),
    "^": (0, -1),
    "v": (0, 1),
}
_MIRRORS: dict[str, Callable[[int, int], tuple[int, int]]] = {
    "/": lambda dx, dy: (-dy, -dx),
    "\\": lambda dx, dy: (dy, dx),
    "|": lambda dx, dy: (-dx, dy),
    "_": lambda dx, dy: (dx, -dy),
    "#": lambda dx, dy: (-dx, -dy),
}


def _hex_digit(step: _Step, command: str) -> None:
    """Push a hexadecimal literal."""
    step.stack.append(int(command, 16))


def _arithmetic(step: _Step, command: str) -> None:
    """Apply a dyadic operator to the top two stack values."""
    right, left = _pop(step.stack), _pop(step.stack)
    step.stack.append(_calculate(command, left, right))


def _arrow(step: _Step, command: str) -> None:
    """Set an absolute direction."""
    step.dx, step.dy = _ARROWS[command]


def _mirror(step: _Step, command: str) -> None:
    """Reflect the direction."""
    step.dx, step.dy = _MIRRORS[command](step.dx, step.dy)


def _random_direction(step: _Step, _command: str) -> None:
    """Turn toward the shell's random draw."""
    if step.random_dir is None:
        _fail("supply a randomness source for this operation")
    step.dx, step.dy = _DIRECTIONS[step.random_dir]


def _trampoline(step: _Step, _command: str) -> None:
    """Skip the next cell."""
    step.x, step.y = _moved(step.x, step.y, step.dx, step.dy, step.width, step.height)


def _conditional_skip(step: _Step, command: str) -> None:
    """Skip the next cell when the stack top is zero."""
    if _pop(step.stack) == 0:
        _trampoline(step, command)


def _teleport(step: _Step, _command: str) -> None:
    """Jump the IP to absolute coordinates."""
    ty, tx = _integer(_pop(step.stack)), _integer(_pop(step.stack))
    if tx < 0 or ty < 0:
        _fail()
    step.x, step.y = tx, ty


def _duplicate(step: _Step, _command: str) -> None:
    """Duplicate the stack top."""
    value = _pop(step.stack)
    step.stack.extend((value, value))


def _drop(step: _Step, _command: str) -> None:
    """Discard the stack top."""
    _pop(step.stack)


def _swap(step: _Step, _command: str) -> None:
    """Swap the top two stack values."""
    one, two = _pop(step.stack), _pop(step.stack)
    step.stack.extend((one, two))


def _rotate_three(step: _Step, _command: str) -> None:
    """Rotate the top three stack values."""
    one, two, three = _pop(step.stack), _pop(step.stack), _pop(step.stack)
    step.stack.extend((one, three, two))


def _rotate_right(step: _Step, _command: str) -> None:
    """Move the stack top to the bottom."""
    if not step.stack:
        _fail("push a value before rotating the stack")
    step.stack.insert(0, step.stack.pop())


def _rotate_left(step: _Step, _command: str) -> None:
    """Move the stack bottom to the top."""
    if not step.stack:
        _fail("push a value before rotating the stack")
    step.stack.append(step.stack.pop(0))


def _reverse(step: _Step, _command: str) -> None:
    """Reverse the stack."""
    step.stack.reverse()


def _stack_length(step: _Step, _command: str) -> None:
    """Push the stack length."""
    step.stack.append(len(step.stack))


def _push_stack(step: _Step, _command: str) -> None:
    """Split the top ``count`` values onto a new stack."""
    count = _integer(_pop(step.stack))
    if count < 0 or count > len(step.stack):
        _fail("use a stack split count from 0 to the current stack length")
    moved = step.stack[-count:] if count else []
    if count:
        del step.stack[-count:]
    step.stacks[-1] = tuple(step.stack)
    step.stacks.append(tuple(moved))
    step.registers.append(None)
    step.commit = False


def _pop_stack(step: _Step, _command: str) -> None:
    """Discard the current stack, merging its values down."""
    if len(step.stacks) == 1:
        step.stack.clear()
        step.registers[0] = None
    else:
        popped = step.stacks.pop()
        step.registers.pop()
        step.stacks[-1] = (*step.stacks[-1], *popped)
        step.commit = False


def _register(step: _Step, _command: str) -> None:
    """Stash the stack top into the register, or recall it."""
    if step.registers[-1] is None:
        step.registers[-1] = _pop(step.stack)
    else:
        step.stack.append(step.registers[-1])
        step.registers[-1] = None


def _get(step: _Step, _command: str) -> None:
    """Push the codebox value at the given coordinates."""
    gy, gx = _integer(_pop(step.stack)), _integer(_pop(step.stack))
    step.stack.append(step.cells.get((gx, gy), 0))


def _put(step: _Step, _command: str) -> None:
    """Write a value into the codebox, growing its bounds."""
    py, px, value = (
        _integer(_pop(step.stack)),
        _integer(_pop(step.stack)),
        _integer(_pop(step.stack)),
    )
    step.cells = _written(step.cells, (px, py), value)
    if px >= 0:
        step.width = max(step.width, px + 1)
    if py >= 0:
        step.height = max(step.height, py + 1)


def _read_char(step: _Step, _command: str) -> None:
    """Push the shell's character input, -1 at EOF."""
    step.stack.append(-1 if step.char_input is None else step.char_input)


def _write_char(step: _Step, _command: str) -> None:
    """Queue a character output effect."""
    step.effect = ("char", _character(_pop(step.stack)))


def _write_number(step: _Step, _command: str) -> None:
    """Queue a numeric output effect."""
    value = _pop(step.stack)
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail()
        if value.is_integer():
            value = int(value)
    step.effect = (
        "num",
        format_integer(value) if isinstance(value, int) else str(value),
    )


def _halt(step: _Step, _command: str) -> None:
    """Halt, leaving the IP unmoved and the stack uncommitted."""
    step.halted = True
    step.commit = False
    step.move = False


def _invalid(_step: _Step, command: str) -> None:
    """Reject an undocumented instruction; spaces and empty cells pass."""
    if command not in _NOP:
        _fail("use an instruction documented by esolangs describe --spec Fish")


#: Command characters to their handlers; anything missing falls back to
#: :func:`_invalid`.
_DISPATCH: dict[str, _Handler] = {
    **dict.fromkeys("0123456789abcdef", _hex_digit),
    **dict.fromkeys("+-*,%()=", _arithmetic),
    **dict.fromkeys("><^v", _arrow),
    **dict.fromkeys("/\\|_#", _mirror),
    "x": _random_direction,
    "!": _trampoline,
    "?": _conditional_skip,
    ".": _teleport,
    ":": _duplicate,
    "~": _drop,
    "$": _swap,
    "@": _rotate_three,
    "}": _rotate_right,
    "{": _rotate_left,
    "r": _reverse,
    "l": _stack_length,
    "[": _push_stack,
    "]": _pop_stack,
    "&": _register,
    "g": _get,
    "p": _put,
    "i": _read_char,
    "o": _write_char,
    "n": _write_number,
    ";": _halt,
}


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
    step = _Step(
        x,
        y,
        dx,
        dy,
        cells,
        list(packed),
        list(register_tuple),
        quote,
        width,
        height,
        char_input,
        random_dir,
    )
    if not _string_step(step, command):
        _DISPATCH.get(command, _invalid)(step, command)
    return step.freeze()


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
