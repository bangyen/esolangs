r"""Interpreter for Super SNUSP.

Super SNUSP is a grid language with a signed sparse tape and value stack.
``"`` starts rightward.  Absent one, the page says "Starts at bottom
right": the IP starts rightward on the last line's last non-space character,
the one reading under which the wiki's Cat (no ``\"``) copies its input.

The execution model is a pure transition over immutable state. The shell
alone handles I/O and random draws, then rebinds the returned state.

Input/output:
    ``,`` reads a character; ``@`` ("Input decimal number") reads a
    whitespace-delimited token and refuses one that is not an integer.  EOF
    propagates.

Errors:
    ProgramError: Empty program.
    InputExhaustedError: ``,`` or ``@`` at EOF.
    ArgumentError: An ``@`` token that is not an integer.
    HaltError: Invalid stack/arithmetic operations (an empty stack read,
        zero divisor, negative shift, bad root, ``.`` on a non-code-point).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from operator import add, and_, mul, or_, sub, xor
from typing import NamedTuple, cast

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.randomness import Randomness, draw
from esolangs.runtime.source_hints import syntax_error, with_hint

_DIRECTIONS = ((0, 1), (1, 0), (0, -1), (-1, 0))
_RULD = (3, 2, 1, 0)
_LURD = (1, 0, 3, 2)
type _Cursor = tuple[int, int, int]
type _Tape = tuple[int, tuple[tuple[int, int], ...]]


class _State(NamedTuple):
    """The pure machine state that `_advance` maps to its successor."""

    cursor: _Cursor
    tape: _Tape
    values: tuple[int, ...]
    digit: bool  # the last command was a digit
    done: bool  # the cursor has left the grid


type _Effect = tuple[str, int] | None


#: The most outcomes one ``=`` may open in a branching search.  Its range is
#: the span between two runtime values rather than a fixed coin, so a single
#: command can ask for more states than any search wants to hold.  This is
#: deliberately a property of the transition rather than the caller's
#: remaining budget: that budget shrinks as the search proceeds, which would
#: make the same program decidable or not depending on when it was reached.
_EQUAL_FANOUT = 256


def _floor_root(value: int, degree: int) -> int:
    if degree <= 0 or (value < 0 and degree % 2 == 0):
        raise HaltError(
            f"';' takes the {degree}-th root of {value}, which has no integer "
            f"value: the degree must be positive, and an even root needs a "
            f"non-negative value",
            hint="use positive root degrees; even degrees need nonnegative radicands",
        )
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
        raise HaltError(
            "the value stack is empty, so there is no top to read",
            hint="push a value before reading or removing the stack top",
        )
    return values[-1]


_COMBINE: dict[str, Callable[[int, int], int]] = {
    "&": and_,
    "*": mul,
    "+": add,
    "-": sub,
    "^": xor,
    "|": or_,
}


def _combine(command: str, value: int, operand: int) -> int:
    """Return the cell ``value`` combined with the stacked ``operand``."""
    if command in _COMBINE:
        return _COMBINE[command](value, operand)
    if command == ";":
        return _floor_root(value, operand)
    if command == ":":
        if not operand:
            raise HaltError(
                f"':' divides {value} by zero",
                hint="ensure the divisor is nonzero before dividing",
            )
        return value // operand
    if operand < 0:
        direction = "left" if command == "[" else "right"
        raise HaltError(
            f"{command!r} shifts {direction} by {operand}, which is negative",
            hint="use a nonnegative shift count",
        )
    return value << operand if command == "[" else value >> operand


class _Context(NamedTuple):
    """What a per-command handler may read: the cell, stack, and shell inputs."""

    command: str
    value: int
    values: tuple[int, ...]
    pointer: int
    heading: int
    char_input: int | None
    number_input: int | None
    random_offset: int | None


class _Outcome(NamedTuple):
    """What a per-command handler changes; a ``None`` field stays as it was."""

    write: int | None = None  # new value for the current cell
    values: tuple[int, ...] | None = None
    pointer: int | None = None
    heading: int | None = None
    steps: int = 1
    effect: _Effect = None
    digit: bool = False  # the command was a digit, so the next one extends it
    done: bool = False  # halt in place instead of moving


def _skip_next(_ctx: _Context) -> _Outcome:
    return _Outcome(steps=2)


def _halt(_ctx: _Context) -> _Outcome:
    return _Outcome(done=True)


def _emit_number(ctx: _Context) -> _Outcome:
    return _Outcome(effect=("num", ctx.value))


def _pop(ctx: _Context) -> _Outcome:
    _top(ctx.values)
    return _Outcome(values=ctx.values[:-1])


def _remainder(ctx: _Context) -> _Outcome:
    divisor = _top(ctx.values)
    if not divisor:
        raise HaltError(
            "'%' takes the remainder by the stacked 0",
            hint="push a nonzero divisor before taking a remainder",
        )
    rem = abs(ctx.value) % abs(divisor)
    return _Outcome(write=-rem if ctx.value < 0 else rem)


def _arithmetic(ctx: _Context) -> _Outcome:
    return _Outcome(write=_combine(ctx.command, ctx.value, _top(ctx.values)))


def _read_char(ctx: _Context) -> _Outcome:
    if ctx.char_input is None:
        raise HaltError(
            "',' reads a character and there is no input left",
            hint="supply another input value or stop reading at end of input",
        )
    return _Outcome(write=ctx.char_input)


def _emit_char(ctx: _Context) -> _Outcome:
    try:
        chr(ctx.value)
    except ValueError:
        raise HaltError(
            hint="keep character output values between 0 and 1114111"
        ) from None
    return _Outcome(effect=("char", ctx.value))


def _reflect_ruld(ctx: _Context) -> _Outcome:
    return _Outcome(heading=_RULD[ctx.heading])


def _reflect_lurd(ctx: _Context) -> _Outcome:
    return _Outcome(heading=_LURD[ctx.heading])


def _random_between(ctx: _Context) -> _Outcome:
    other = _top(ctx.values)
    if ctx.random_offset is None:
        raise HaltError(
            "'=' needs a random draw and none was supplied",
            hint="supply a randomness source for this operation",
        )
    low, high = sorted((ctx.value, other))
    if not 0 <= ctx.random_offset <= high - low:
        raise HaltError(
            f"'=' was given the draw {ctx.random_offset}, outside the "
            f"0..{high - low} its range {low}..{high} allows",
            hint="supply a random draw within the stated range",
        )
    return _Outcome(write=low + ctx.random_offset, values=ctx.values[:-1])


def _decrement(ctx: _Context) -> _Outcome:
    return _Outcome(write=ctx.value - 1)


def _increment(ctx: _Context) -> _Outcome:
    return _Outcome(write=ctx.value + 1)


def _move_left(ctx: _Context) -> _Outcome:
    return _Outcome(pointer=ctx.pointer - 1)


def _move_right(ctx: _Context) -> _Outcome:
    return _Outcome(pointer=ctx.pointer + 1)


def _skip_if_zero(ctx: _Context) -> _Outcome:
    return _Outcome(steps=2 if ctx.value == 0 else 1)


def _read_number(ctx: _Context) -> _Outcome:
    if ctx.number_input is None:
        raise HaltError(
            "'@' reads a number and there is no input left",
            hint="supply another input value or stop reading at end of input",
        )
    return _Outcome(write=ctx.number_input)


def _negate(ctx: _Context) -> _Outcome:
    return _Outcome(write=-ctx.value)


def _skip_if_negative(ctx: _Context) -> _Outcome:
    return _Outcome(steps=2 if ctx.value < 0 else 1)


def _push(ctx: _Context) -> _Outcome:
    return _Outcome(values=(*ctx.values, ctx.value))


def _pop_to_cell(ctx: _Context) -> _Outcome:
    return _Outcome(write=_top(ctx.values))


def _invert(ctx: _Context) -> _Outcome:
    return _Outcome(write=~ctx.value)


def _letter(ctx: _Context) -> _Outcome:
    return _Outcome(write=ord(ctx.command))


def _no_op(_ctx: _Context) -> _Outcome:
    return _Outcome()


#: Per-command handlers; digits and letters are ranges, so `_advance`
#: handles those two before consulting this table.
_HANDLERS: dict[str, Callable[[_Context], _Outcome]] = {
    "!": _skip_next,
    "'": _halt,
    "#": _emit_number,
    "$": _pop,
    "%": _remainder,
    ",": _read_char,
    ".": _emit_char,
    "/": _reflect_ruld,
    "\\": _reflect_lurd,
    "=": _random_between,
    "(": _decrement,
    ")": _increment,
    "<": _move_left,
    ">": _move_right,
    "?": _skip_if_zero,
    "@": _read_number,
    "_": _negate,
    "`": _skip_if_negative,
    "{": _push,
    "}": _pop_to_cell,
    "~": _invert,
    **dict.fromkeys("&*+-:;[]^|", _arithmetic),
}


def _advance(
    state: _State,
    code: Sequence[str],
    char_input: int | None = None,
    number_input: int | None = None,
    random_offset: int | None = None,
) -> tuple[_State, _Effect]:
    """Return the pure next state and an output effect, if this cell emits."""
    (row, col, heading), (pointer, cells), values, last_digit, done = state
    if done:
        return state, None
    command = code[row][col]
    value = _read(cells, pointer)
    if command in "0123456789":
        outcome = _Outcome(
            write=(10 * value if last_digit else 0) + int(command), digit=True
        )
    else:
        handler = _HANDLERS.get(command)
        if handler is None:
            is_letter = "A" <= command <= "Z" or "a" <= command <= "z"
            handler = _letter if is_letter else _no_op
        outcome = handler(
            _Context(
                command,
                value,
                values,
                pointer,
                heading,
                char_input,
                number_input,
                random_offset,
            )
        )
    if outcome.done:
        return state._replace(done=True, digit=False), None
    if outcome.write is not None:
        cells = _write(cells, pointer, outcome.write)
    if outcome.values is not None:
        values = outcome.values
    if outcome.pointer is not None:
        pointer = outcome.pointer
    if outcome.heading is not None:
        heading = outcome.heading
    d_row, d_col = _DIRECTIONS[heading]
    row += d_row * outcome.steps
    col += d_col * outcome.steps
    done = not (0 <= row < len(code) and 0 <= col < len(code[0]))
    return _State(
        (row, col, heading), (pointer, cells), values, outcome.digit, done
    ), outcome.effect


class _Machine:
    """Protocol shell holding one immutable Super SNUSP state value."""

    def __init__(
        self, code: Sequence[str], io: IO, rng: Randomness | None = None
    ) -> None:
        if not code or not (width := max(map(len, code), default=0)):
            raise syntax_error(
                "Super SNUSP program cannot be empty",
                ("provide a nonempty grid with an entry point and a terminating path"),
            )
        self.code = tuple(row.ljust(width) for row in code)
        self.io, self._rng = io, rng
        starts = [
            (r, c)
            for r, line in enumerate(self.code)
            for c, char in enumerate(line)
            if char == '"'
        ]
        if not starts:
            lines = [r for r, line in enumerate(code) if line.strip()] or [0]
            starts = [(lines[-1], len(code[lines[-1]].rstrip()) - 1)]
        row, col, heading = (*starts[0], 0)
        self.state = _State((row, col, heading), (0, ()), (), digit=False, done=False)

    @property
    def halted(self) -> bool:
        return self.state.done

    #: ``ip`` is a cell of the program's own rectangle: the first two
    #: parts are a row and a column, and the rest is a heading.  Without
    #: this a caller cannot tell the pair from a call depth or a frame
    #: stack, which look identical and mean somewhere else entirely.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...] | None:
        return None if self.halted else self.state.cursor

    @property
    def memory(self) -> list[int]:
        return [value for _, value in self.state.tape[1]]

    @property
    def stack(self) -> list[object]:
        return list(self.state.values)

    def snapshot(self) -> tuple[object, ...]:
        state = self.state
        pointer, cells = state.tape
        return (
            *state.cursor,
            pointer,
            cells,
            state.values,
            state.digit,
            state.done,
            self.io.progress(),
        )

    # The all-random-outcomes search.  ``_State`` is already the whole
    # machine -- ``done`` included -- so the branching state is that value
    # unchanged, minus the input cursor ``snapshot`` adds: input is declined
    # below rather than forked, and output cannot affect a later command.

    def branching_snapshot(self) -> _State:
        """Return the current state as the search's starting point."""
        return self.state

    def branching_halted(self, state: object) -> bool:
        """Report whether ``state`` has left the grid."""
        return cast(_State, state).done

    def branching_successors(
        self, state: object, _limit: int
    ) -> tuple[_State, ...] | None:
        """Return the state for every value ``=`` could store.

        Mirrors :meth:`step`'s draw *condition*: an ``=`` with nothing on the
        stack draws nothing and raises inside the transition, so it is left
        to the single deterministic call rather than forked over an empty
        range.

        The range is the inclusive span between the current cell and the
        stack top, unbounded in principle (unlike a coin or a heading), so
        it is charged against ``limit`` here rather than materialized first.

        A :class:`~esolangs.exceptions.HaltError` from the transition
        propagates, as out of :meth:`step`: it means the program halted on an
        invalid operation, and catching it would hide a *terminating* branch
        and let the search report a universal hang for a program that stops.
        """
        current = cast(_State, state)
        row, col, _ = current.cursor
        pointer, cells = current.tape
        values = current.values
        command = self.code[row][col]
        if command in ",@":
            return None

        offsets: tuple[int | None, ...] = (None,)
        if command == "=" and values:
            low, high = sorted((_read(cells, pointer), values[-1]))
            if high - low + 1 > _EQUAL_FANOUT:
                raise with_hint(
                    TimeoutError(
                        f"undecided: one '=' spanning {high - low + 1} values exceeds "
                        f"the {_EQUAL_FANOUT}-outcome cap on a single transition"
                    ),
                    (
                        f"keep the random range within {_EQUAL_FANOUT} values; "
                        "limit does not raise this transition cap"
                    ),
                )
            offsets = tuple(range(high - low + 1))

        return tuple(
            _advance(current, self.code, None, None, offset)[0] for offset in offsets
        )

    def step(self) -> None:
        if self.halted:
            return
        (row, col, _), (pointer, cells) = self.state.cursor, self.state.tape
        values = self.state.values
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
    drive(machine)


if __name__ == "__main__":
    script_main(run, shape="strip")
