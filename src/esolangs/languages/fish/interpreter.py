r"""Fish (``><>``): a fish swims a codebox, with a stack of stacks.

The fish starts top left swimming right and wraps at the edges of the box.
Each cell it swims through is a command:

- ``> < ^ v`` set the heading; ``/ \ | _ #`` are mirrors it bounces off.
  ``x`` turns at random.  ``!`` skips the next cell, ``?`` pops and skips
  it on zero, ``.`` pops ``y``, ``x`` and jumps there.
- ``0``-``9`` and ``a``-``f`` push a hex digit.  ``+ - * , %`` pop ``a``,
  then ``b``, and push ``b op a`` (``,`` divides); ``= ( )`` push ``b == a``,
  ``b < a``, ``b > a`` as 1 or 0.
- ``'`` or ``"`` starts string mode, which pushes each cell's codepoint
  until the same quote ends it.
- ``:`` duplicates, ``~`` drops, ``$`` swaps the top two, ``@`` moves the
  top under the next two.  ``}`` and ``{`` rotate the whole stack right and
  left, ``r`` reverses it, ``l`` pushes its length.
- ``[`` pops ``n`` and moves the top ``n`` values onto a new stack; ``]``
  pours the current stack back into the one below (or empties the last).
  ``&`` moves the top into the stack's register, or the register back.
- ``g`` pops ``y``, ``x`` and pushes that cell; ``p`` pops ``y``, ``x``,
  ``v`` and writes ``v`` there.  ``i`` reads a character (-1 at EOF), ``o``
  prints one, ``n`` prints a number.  ``;`` halts.  A space does nothing.

This is the current non-threaded language.  Cells hold raw Unicode
codepoints; counts and coordinates must be integral.  ``p`` may grow the
box's positive bounds and use negative coordinates as storage.  An IP that
``.`` sends past the box re-enters it modulo the box's size; the spec leaves
this open, and fish.py instead walks the empty cells to the edge.  Division
is Python's true division, matching the spec's floating result.  ``o``
needs an integral codepoint.  Only a space and an empty cell are no-ops: a
tab, or a control character ``p`` writes, is an invalid instruction.  A
string pushes an empty cell (past a short row) as 0, its ``g`` value;
fish.py pushes a space, as it stores spaces as 0.  Invalid instructions,
stack underflow, and division by zero raise
:class:`~esolangs.exceptions.HaltError`; an empty program raises
:class:`ValueError`.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
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


#: Dyadic operators by command character.
_OPERATORS: dict[str, Callable[[Number, Number], Number]] = {
    "+": lambda left, right: left + right,
    "-": lambda left, right: left - right,
    "*": lambda left, right: left * right,
    ",": lambda left, right: left / _nonzero(right),
    "%": lambda left, right: left % _nonzero(right),
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


def _output(command: str, value: Number) -> _Effect:
    """Return the effect of ``o`` (a character) or ``n`` (a number's text)."""
    if command == "o":
        return "char", _character(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail()
        if value.is_integer():
            value = int(value)
    return "num", format_integer(value) if isinstance(value, int) else str(value)


def _coordinates(stack: list[Number]) -> tuple[int, int]:
    """Pop ``y``, then ``x``, as ``.``, ``g`` and ``p`` do."""
    y, x = _integer(_pop(stack)), _integer(_pop(stack))
    return x, y


def _destination(stack: list[Number]) -> tuple[int, int]:
    """Pop where ``.`` jumps: negative cells are storage, never code."""
    x, y = _coordinates(stack)
    if x < 0 or y < 0:
        _fail()
    return x, y


def _rotated(stack: list[Number], shift: int) -> list[Number]:
    """Rotate the stack: ``shift`` -1 moves the top to the bottom, 1 back."""
    if not stack:
        _fail("push a value before rotating the stack")
    return stack[shift:] + stack[:shift]


#: Commands that only touch the stack top: how many they pop (top first), and
#: what they push in its place.
_STACK_OPS: dict[str, tuple[int, Callable[..., tuple[Number, ...]]]] = {
    **{digit: (0, lambda d=int(digit, 16): (d,)) for digit in "0123456789abcdef"},
    **{op: (2, lambda a, b, op=op: (_calculate(op, b, a),)) for op in _OPERATORS},
    ":": (1, lambda a: (a, a)),
    "~": (1, lambda _a: ()),
    "$": (2, lambda a, b: (a, b)),
    "@": (3, lambda a, b, c: (a, c, b)),
}
#: Commands that rearrange the whole stack.
_SHUFFLES: dict[str, Callable[[list[Number]], list[Number]]] = {
    "}": lambda stack: _rotated(stack, -1),
    "{": lambda stack: _rotated(stack, 1),
    "r": lambda stack: stack[::-1],
    "l": lambda stack: [*stack, len(stack)],
}
#: Arrows set the heading; mirrors reflect it.
_TURNS: dict[str, Callable[[int, int], tuple[int, int]]] = {
    ">": lambda _dx, _dy: (1, 0),
    "<": lambda _dx, _dy: (-1, 0),
    "^": lambda _dx, _dy: (0, -1),
    "v": lambda _dx, _dy: (0, 1),
    "/": lambda dx, dy: (-dy, -dx),
    "\\": lambda dx, dy: (dy, dx),
    "|": lambda dx, dy: (-dx, dy),
    "_": lambda dx, dy: (dx, -dy),
    "#": lambda dx, dy: (-dx, -dy),
}


def _scope(
    command: str,
    stacks: tuple[tuple[Number, ...], ...],
    registers: tuple[Number | None, ...],
    stack: list[Number],
) -> tuple[tuple[tuple[Number, ...], ...], tuple[Number | None, ...], list[Number]]:
    """Apply ``[``, ``]`` or ``&``; ``stack`` is the uncommitted top of ``stacks``.

    Return the stacks (the caller overwrites the last with the new top), the
    registers, and the new top.  ``&`` fills an empty register, else empties it.
    """
    match command:
        case "[":
            count = _integer(_pop(stack))
            if not 0 <= count <= len(stack):
                _fail("use a stack split count from 0 to the current stack length")
            split = len(stack) - count
            return (
                (*stacks[:-1], tuple(stack[:split]), ()),
                (*registers, None),
                stack[split:],
            )
        case "]" if len(stacks) == 1:
            return stacks, (None,), []
        case "]":
            return stacks[:-1], registers[:-1], [*stacks[-2], *stack]
        case _ if registers[-1] is None:
            return stacks, (*registers[:-1], _pop(stack)), stack
        case _:
            return stacks, (*registers[:-1], None), [*stack, registers[-1]]


# :func:`_advance` is the pure transition over an immutable :data:`_Core`; the
# ``i`` value arrives already read, and ``x``'s direction already drawn.
# :meth:`_Machine.step` is the shell that reads, draws, and writes the effect.
def _advance(
    state: _Core,
    char_input: int | None = None,
    random_dir: int | None = None,
) -> tuple[_Core, _Effect]:
    """Return the next core and any output effect for the cell at the IP.

    Pure.  ``char_input`` is what ``i`` pushes (``None`` is EOF, so -1);
    ``random_dir`` is the draw ``x`` selects from.  The shell supplies both.
    """
    x, y, dx, dy, cells, stacks, registers, quote, halted, width, height = state
    if halted:
        return state, None
    command = _character(cells.get((x, y), 0))
    stack = list(stacks[-1])
    effect: _Effect = None
    if quote is not None:
        if command == quote:
            quote = None
        else:
            stack.append(ord(command))
    elif command in _STACK_OPS:
        arity, operation = _STACK_OPS[command]
        popped = [_pop(stack) for _ in range(arity)]
        stack += operation(*popped)
    elif command in _SHUFFLES:
        stack = _SHUFFLES[command](stack)
    elif command in _TURNS:
        dx, dy = _TURNS[command](dx, dy)
    else:
        match command:
            case "'" | '"':
                quote = command
            case "x":
                if random_dir is None:
                    _fail("supply a randomness source for this operation")
                dx, dy = _DIRECTIONS[random_dir]
            case "!" | "?":
                if command == "!" or _pop(stack) == 0:
                    x, y = _moved(x, y, dx, dy, width, height)
            case ".":
                x, y = _destination(stack)
            case "[" | "]" | "&":
                stacks, registers, stack = _scope(command, stacks, registers, stack)
            case "g":
                stack.append(cells.get(_coordinates(stack), 0))
            case "p":
                px, py = _coordinates(stack)
                cells = _written(cells, (px, py), _integer(_pop(stack)))
                width, height = max(width, px + 1), max(height, py + 1)
            case "i":
                stack.append(-1 if char_input is None else char_input)
            case "o" | "n":
                effect = _output(command, _pop(stack))
            case ";":
                halted = True
                return (
                    x,
                    y,
                    dx,
                    dy,
                    cells,
                    stacks,
                    registers,
                    quote,
                    halted,
                    width,
                    height,
                ), None
            case _ if command not in _NOP:
                _fail("use an instruction documented by esolangs describe --spec Fish")
    stacks = (*stacks[:-1], tuple(stack))
    x, y = _moved(x, y, dx, dy, width, height)
    return (
        x,
        y,
        dx,
        dy,
        cells,
        stacks,
        registers,
        quote,
        halted,
        width,
        height,
    ), effect


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
