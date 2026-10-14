r"""Befunge-93: the program is a grid, and a pointer walks it.

The pointer starts top left heading right, carries one stack, and wraps at
the edges of an 80x25 torus.  Each cell it lands on is a command:

- ``0``-``9`` push a digit.  ``+ - * / %`` pop ``a``, then ``b``, and push
  ``b op a``; ``!`` pushes ``not a``, and `` ` `` pushes ``b > a``.
- ``:`` duplicates the top, ``\`` swaps the top two, ``$`` drops one.
- ``> v < ^`` set the heading and ``?`` picks one at random.  ``_`` pops
  and heads right on zero, else left; ``|`` heads down on zero, else up.
  ``#`` jumps over the next cell.
- ``"`` toggles string mode, which pushes every cell it crosses as a byte.
- ``g`` pops ``y``, ``x`` and pushes that cell; ``p`` pops ``y``, ``x``,
  ``v`` and writes ``v`` there, so a program can rewrite itself.
- ``.`` prints a number and a space, ``,`` a character; ``&`` reads a
  number, ``~`` a character.  ``@`` halts.  Any other byte does nothing.

Where the spec is silent this follows the C reference interpreter: division
truncates toward zero (the wiki says "rounded down", but -7 / 2 is -3), and
a zero divisor reads the result from the user, raising
:class:`~esolangs.exceptions.HaltError` if none is left.  A pop off the
empty stack yields 0, ``g`` outside the grid pushes 0, ``p`` outside is
ignored.  Values must fit a C signed long, else HaltError.  Cells are
bytes.  EOF on ``&`` or ``~`` propagates.  An empty or oversized program
raises :class:`ValueError` (spaces past column 80 are dropped, not counted).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from ctypes import c_long, sizeof
from typing import NamedTuple, cast

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.memory import trunc_div, trunc_mod
from esolangs.runtime.randomness import Randomness, draw
from esolangs.runtime.source_hints import syntax_error

#: ``?`` picks one, in the order the shell's draw maps to: right, down, left, up.
_DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))
_HEADINGS = dict(zip(">v<^", _DIRECTIONS, strict=True))
#: ``_`` and ``|``: the heading on a popped zero, and on anything else.
_BRANCHES = {"_": ((1, 0), (-1, 0)), "|": ((0, 1), (0, -1))}
#: Commands that read from outside the state; a zero divisor reads too.
_READS = {"~": "char", "&": "number", "?": "draw"}
#: Commands that only touch the stack: how many they pop (top first), and
#: what they push in its place.
_STACK_OPS: dict[str, tuple[int, Callable[..., tuple[int, ...]]]] = {
    **{digit: (0, lambda d=int(digit): (d,)) for digit in "0123456789"},
    "+": (2, lambda a, b: (b + a,)),
    "-": (2, lambda a, b: (b - a,)),
    "*": (2, lambda a, b: (b * a,)),
    "!": (1, lambda a: (int(not a),)),
    "`": (2, lambda a, b: (int(b > a),)),
    ":": (1, lambda a: (a, a)),
    "\\": (2, lambda a, b: (a, b)),
    "$": (1, lambda _a: ()),
}
_WIDTH = 80
_HEIGHT = 25
_LONG_BITS = sizeof(c_long) * 8
_MIN_VALUE = -(1 << (_LONG_BITS - 1))
_MAX_VALUE = (1 << (_LONG_BITS - 1)) - 1
type _Cursor = tuple[int, int, int, int]
type _Grid = tuple[tuple[str, ...], ...]
#: Persistent cons cells keep push/pop O(1) without changing old states.
type _Stack = tuple[int, _Stack] | None


class _State(NamedTuple):
    cursor: _Cursor
    grid: _Grid
    stack: _Stack
    string: bool
    done: bool


type _Effect = str | None


def _pop(stack: _Stack) -> tuple[int, _Stack]:
    """Return the top and the rest; an empty stack reads as 0."""
    return (0, None) if stack is None else stack


def _pops(stack: _Stack, count: int) -> tuple[tuple[int, ...], _Stack]:
    """Return the top ``count`` values, top first, and the rest."""
    values = []
    for _ in range(count):
        value, stack = (0, None) if stack is None else stack
        values.append(value)
    return tuple(values), stack


def _push(stack: _Stack, *values: int) -> _Stack:
    """Return a stack with the values pushed in order."""
    if any(value < _MIN_VALUE or value > _MAX_VALUE for value in values):
        raise HaltError("Befunge integer exceeds signed-long range")
    for value in values:
        stack = (value, stack)
    return stack


def _divide(a: int, b: int, command: str, number_input: int | None) -> int:
    """Return ``b / a`` or ``b % a``, with the quotient truncated toward zero.

    On a zero divisor the result is read from the user instead; with no
    input left that raises :class:`HaltError`.
    """
    if not a:
        if number_input is None:
            raise HaltError(
                f"'{command}' divides by zero and needs a result",
                hint="ensure the divisor is nonzero before dividing",
            )
        return number_input
    return trunc_div(b, a) if command == "/" else trunc_mod(b, a)


def _values(stack: _Stack) -> tuple[int, ...]:
    """Return the stack in bottom-to-top order without recursive traversal."""
    values = []
    while stack is not None:
        value, stack = stack
        values.append(value)
    return tuple(reversed(values))


def _supplied(value: int | None, command: str, what: str) -> int:
    """Return an input the shell read for ``command``; refuse a missing one."""
    if value is None:
        raise HaltError(
            f"'{command}' reads {what} and there is no input left",
            hint="supply another input value or stop reading at end of input",
        )
    return value


def _put(grid: _Grid, x: int, y: int, value: int) -> _Grid:
    """Return the grid with cell (x, y) set to a byte; outside, unchanged."""
    if not (0 <= y < len(grid) and 0 <= x < len(grid[0])):
        return grid
    row = (*grid[y][:x], chr(value & 0xFF), *grid[y][x + 1 :])
    return (*grid[:y], row, *grid[y + 1 :])


def _reads(state: _State) -> str | None:
    """Name what the next command takes from outside the state, if anything.

    ``"char"`` for ``~``, ``"number"`` for ``&``, ``"divisor"`` for a zero
    divisor (an empty stack pops as 0, so ``/`` alone reads too), and
    ``"draw"`` for ``?``.  String mode reads nothing: it pushes the cell.
    """
    (col, row, _dx, _dy), grid, stack, string, done = state
    if done or string:
        return None
    command = grid[row][col]
    if command in "/%" and _pop(stack)[0] == 0:
        return "divisor"
    return _READS.get(command)


def _advance(
    state: _State,
    char_input: int | None = None,
    number_input: int | None = None,
    random_dir: int | None = None,
) -> tuple[_State, _Effect]:
    """Run the cell under the pointer, then move one cell along the heading.

    Inputs come from the shell, which reads what :func:`_reads` names; the
    result is the next state and the text this cell prints, if any.
    """
    (col, row, dx, dy), grid, stack, string, done = state
    if done:
        return state, None
    command, effect = grid[row][col], None
    if string and command != '"':
        stack = _push(stack, ord(command))
    elif command in _STACK_OPS:
        arity, operation = _STACK_OPS[command]
        popped, stack = _pops(stack, arity)
        stack = _push(stack, *operation(*popped))
    else:
        match command:
            case '"':
                string = not string
            case ">" | "v" | "<" | "^":
                dx, dy = _HEADINGS[command]
            case "?":
                if random_dir is None:
                    raise HaltError(
                        "'?' needs a random draw and none was supplied",
                        hint="supply a randomness source for this operation",
                    )
                dx, dy = _DIRECTIONS[random_dir]
            case "_" | "|":
                a, stack = _pop(stack)
                dx, dy = _BRANCHES[command][bool(a)]
            case "#":
                col, row = (col + dx) % len(grid[0]), (row + dy) % len(grid)
            case "/" | "%":
                (a, b), stack = _pops(stack, 2)
                stack = _push(stack, _divide(a, b, command, number_input))
            case ".":
                a, stack = _pop(stack)
                effect = f"{a} "
            case ",":
                a, stack = _pop(stack)
                effect = chr(a & 0xFF)
            case "g":
                (y, x), stack = _pops(stack, 2)
                in_grid = 0 <= y < len(grid) and 0 <= x < len(grid[0])
                stack = _push(stack, ord(grid[y][x]) if in_grid else 0)
            case "p":
                (y, x, value), stack = _pops(stack, 3)
                grid = _put(grid, x, y, value)
            case "&":
                stack = _push(stack, _supplied(number_input, "&", "a number"))
            case "~":
                stack = _push(stack, _supplied(char_input, "~", "a character"))
            case "@":
                done = True
    col, row = (col + dx) % len(grid[0]), (row + dy) % len(grid)
    return _State((col, row, dx, dy), grid, stack, string, done), effect


class _Machine:
    """Protocol shell holding one immutable Befunge state value."""

    #: The first draw is a fact about the program, so a seed makes it repeat.
    reproducible_seed = 0

    def __init__(
        self, code: Sequence[str], io: IO, rng: Randomness | None = None
    ) -> None:
        # Spaces past column 80 are no content: the torus is 80 wide either
        # way.  The wiki's FizzBuzz and short 99 Bottles carry such padding.
        code = [row[:_WIDTH] if not row[_WIDTH:].strip(" ") else row for row in code]
        if not code or not (width := max(map(len, code), default=0)):
            raise syntax_error(
                "Befunge program cannot be empty",
                "provide a nonempty grid; @ halts immediately",
            )
        if width > _WIDTH or len(code) > _HEIGHT:
            raise syntax_error(
                "Befunge program exceeds its 80x25 playfield",
                "keep each row at most 80 characters and the grid at most 25 rows",
            )
        if any(ord(char) > 0xFF for row in code for char in row):
            raise ValueError("Befunge source cells must be bytes")
        rows = [row.ljust(_WIDTH) for row in code]
        rows.extend(" " * _WIDTH for _ in range(_HEIGHT - len(rows)))
        self.grid = tuple(tuple(row) for row in rows)
        self.io, self._rng = io, rng
        self.state = _State((0, 0, 1, 0), self.grid, None, string=False, done=False)

    @property
    def halted(self) -> bool:
        return self.state.done

    #: ``ip`` is a cell of the program's own rectangle: a column and a row,
    #: then the heading, so a caller can draw it rather than guess.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...] | None:
        col, row, dx, dy = self.state.cursor
        return None if self.halted else (row, col, dx, dy)

    @property
    def stack(self) -> list[object]:
        return list(_values(self.state.stack))

    def snapshot(self) -> tuple[object, ...]:
        cursor, grid, stack, string, done = self.state
        return (*cursor, grid, _values(stack), string, done, self.io.progress())

    def branching_snapshot(self) -> _State:
        """Return the current state as the hang search's starting point."""
        return self.state

    def branching_halted(self, state: object) -> bool:
        """Report whether ``state`` has reached ``@``."""
        return cast(_State, state).done

    def branching_successors(
        self, state: object, _limit: int
    ) -> tuple[_State, ...] | None:
        """Return one state per direction ``?`` could take.

        ``None`` for an input cell, whose read cannot be forked.  A
        transition that raises is left to propagate, as it does from
        :meth:`step`: catching it would hide a halting branch.
        """
        current = cast(_State, state)
        if current.done:
            return (current,)
        match _reads(current):
            case None:
                return (_advance(current)[0],)
            case "draw":
                return tuple(_advance(current, random_dir=d)[0] for d in range(4))
            case _:
                return None  # a read cannot be forked

    def step(self) -> None:
        if self.halted:
            return
        reads = _reads(self.state)
        char_input = self.io.input_char() if reads == "char" else None
        number_input = None
        if reads in ("number", "divisor"):
            try:
                number_input = self.io.input_num()
            except EOFError:
                # `&` is a plain read: its EOF propagates.  A zero divisor
                # gets no result instead, and halts as documented.
                if reads == "number":
                    raise
        random_dir = draw(self._rng, 4) if reads == "draw" else None
        self.state, effect = _advance(self.state, char_input, number_input, random_dir)
        if effect is not None:
            self.io.print_str(effect)


def run(code: list[str], io: IO, rng: Randomness | None = None) -> None:
    """Execute a Befunge grid."""
    machine = _Machine(code, io, rng)
    drive(machine)


if __name__ == "__main__":
    script_main(run, shape="strip")
