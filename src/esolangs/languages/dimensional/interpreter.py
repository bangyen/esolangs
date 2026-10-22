"""Interpreter for Dimensional v3.0.

Dimensional v3.0 (the current wiki spec) is a hierarchy of pointers: an
``n``-pointer (n > 1) is an infinite-dimensional pointer whose position
contains an ``(n-1)``-slot, and a ``1``-slot holds an unsigned byte.  The
value is the byte reached by following the chain of pointers from the
selected axis down to level 2.  ``$AXIS`` picks which pointer the move and
loop commands act on; moving a higher pointer selects a fresh lower slot, so
moving away and back to the origin restores the previous tape.  Cells wrap
at 8 bits (unsigned bytes), ``:CHAR`` above 255 included.

Commands:
    ``>d`` / ``<d``: move the axis pointer along dimension ``d`` (bare
        ``>`` / ``<`` use the value as the dimension).
    ``+`` / ``-``: adjust the value.
    ``:CH`` / ``=HEX``: set the value from the source.
    ``.``: print the value.
    ``,`` / ``d`` / ``x``: read the value from input.
    ``[`` / ``]``: loop on the value.
    ``{d`` / ``}``: loop on the axis pointer's dimension-``d`` coordinate.
    ``?d`` / ``!d``: read / clear that coordinate.
    ``$AXIS``: select the pointer.
    ``*``: toggle comment mode.

Input/output:
    ``,`` reads a character, ``d`` a decimal number and ``x`` a hexadecimal
    one.  Exhausted input raises (the repo-wide convention).

Errors:
    ProgramError: A ``:`` or ``=`` at the end of a program, or a malformed
        ``=`` literal, before the run starts; unmatched ``[``/``]`` or
        ``{``/``}``; an ``x`` read of a token that is not hexadecimal.
    InputExhaustedError: ``,``, ``d`` or ``x`` at EOF.
    ArgumentError: A ``d`` token that is not an integer.

Decisions:
    The v3.0 wiki leaves some details open; these are documented choices, not
    part of any written spec.
    * The pointer axis defaults to 2 (the innermost pointer, which addresses
      bytes directly), so ``>0``/``<0`` with no ``$AXIS`` is a linear byte
      tape.
    * ``d`` and ``x`` read a decimal/hexadecimal number from input (like
      ``,`` reads a character).
    * ``$AXIS`` values below 2 are clamped to 2 (there is no 1-pointer).
    * Unmatched brackets are rejected, matching the package's other tape
      interpreters.  The two pairs nest independently, so ``[{]}`` is
      accepted.
    * The table writes ``{DIMENSION``, ``?DIMENSION``, ``!DIMENSION`` and
      ``$AXIS`` with an operand; without one, the dimension is 0 and the axis
      2 (a clean-room reading rejects the program instead).
    * ``d`` and ``x`` ("Accepts a number written in decimal") read one
      whitespace-delimited token and leave the delimiter, so a following
      ``,`` reads it; reading the whole line is the other reading.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast, overload

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.brackets import unmatched
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error


class _Level:
    """One pointer level: its position plus the slots it can select.

    For level 2 the selected "slot" is the byte value itself; for higher
    levels it is the :class:`_Level` one step down the chain.
    """

    __slots__ = ("level", "pos", "slots")

    def __init__(self, level: int) -> None:
        self.level = level
        self.pos: dict[int, int] = {}
        self.slots: dict[tuple[tuple[int, int], ...], object] = {}

    def key(self) -> tuple[tuple[int, int], ...]:
        return tuple(sorted((k, v) for k, v in self.pos.items() if v))

    def child(self) -> object:
        """Return the structure at the current position (fresh if first visit)."""
        key = self.key()
        child = self.slots.get(key)
        if child is None:
            child = _Level(self.level - 1) if self.level > 2 else 0
            self.slots[key] = child
        return child

    def freeze(self) -> tuple[object, ...]:
        """Return a hashable snapshot of this level's position and slots."""
        return (
            self.key(),
            tuple(
                sorted(
                    (k, v.freeze() if isinstance(v, _Level) else v)
                    for k, v in self.slots.items()
                )
            ),
        )


class _Tape:
    """The pointer hierarchy, current axis, and the byte it addresses.

    Not the steppable machine -- that is :class:`_Machine`, which holds one
    of these.  This is the language's memory: a chain of :class:`_Level`
    pointers, each selecting either the byte (at level 2) or the level
    below it.
    """

    def __init__(self) -> None:
        self.axis = 2
        self.top = _Level(2)

    def node_at(self, level: int) -> _Level:
        """Return the level-``level`` pointer on the current path (growing the top)."""
        while self.top.level < level:
            old = self.top
            env = _Level(old.level + 1)
            env.slots[()] = old  # the origin of the envelope holds the old tape
            self.top = env
        node = self.top
        while node.level > level:
            node = cast(_Level, node.child())
        return node

    def value(self) -> int:
        return cast(int, self.node_at(2).child())

    def peek_value(self) -> int:
        """Return the addressed byte without allocating an unvisited slot."""
        node = self.top
        while node.level > 2:
            child = node.slots.get(node.key())
            if child is None:
                return 0
            node = cast(_Level, child)
        return cast(int, node.slots.get(node.key(), 0))

    def set_value(self, value: int) -> None:
        node = self.node_at(2)
        node.slots[node.key()] = value % 256

    def move(self, dim: int, delta: int) -> None:
        node = self.node_at(self.axis)
        node.pos[dim] = node.pos.get(dim, 0) + delta

    def coord(self, dim: int) -> int:
        return self.node_at(self.axis).pos.get(dim, 0)

    def clear(self, dim: int) -> None:
        self.node_at(self.axis).pos.pop(dim, None)


def _matches(code: str) -> dict[int, int]:
    """Map each bracket to its partner, ignoring comment regions."""
    stacks: dict[str, list[int]] = {"[": [], "{": []}
    res: dict[int, int] = {}
    comment = False
    operand_end = 0
    for i, char in enumerate(code):
        if i < operand_end:
            continue
        if comment:
            if char == "*":
                comment = False
            continue
        if char in ":=":
            # Literal payloads are data, including bracket and comment glyphs.
            operand_end = i + (2 if char == ":" else 3)
            # A malformed literal rejects the program before it runs, as an
            # unmatched bracket does, rather than when (or if) it executes.
            _advance((i + 1, False, 2), code, {}, lambda: 0, lambda _d: 0)
        elif char == "*":
            comment = True
        elif char in "[{":
            stacks[char].append(i)
        elif char in "]}":
            stack = stacks["[" if char == "]" else "{"]
            if not stack:
                raise unmatched(char, i)
            open_i = stack.pop()
            res[open_i] = i
            res[i] = open_i
    for opener, stack in stacks.items():
        if stack:
            raise unmatched(opener, stack[-1])
    return res


@overload
def _number(code: str, ind: int, default: int) -> tuple[int, int]: ...
@overload
def _number(code: str, ind: int, default: None) -> tuple[int | None, int]: ...
def _number(code: str, ind: int, default: int | None) -> tuple[int | None, int]:
    """Parse an optional ``~``-prefixed number at ``ind``; ``None`` if absent."""
    if ind >= len(code):
        return default, ind
    neg = False
    if code[ind] == "~":
        neg = True
        ind += 1
    if ind < len(code) and code[ind].isdigit():
        j = ind
        while j < len(code) and code[j].isdigit():
            j += 1
        dim = int(code[ind:j])
        return (-dim if neg else dim), j
    return default, ind


#: One instant of a run: ``(ind, comment, axis)`` -- the code cursor,
#: whether a ``*`` region is open, and how many pointer levels ``$`` has
#: asked for.
#:
#: The tape is *not* here.  It is a chain of lazily grown levels holding
#: sparse maps, so freezing one per step would rebuild the whole structure
#: for every command -- the cost that once made a test 1300x
#: slower.  Nothing shares a level, so there is no aliasing to preserve
#: either: the transition names what it wants done to the tape and the
#: shell does it.
type _State = tuple[int, bool, int]


#: What a command wants done to the tape.  Every Dimensional command makes
#: at most one such change, so this is the single-effect shape
#: rather than the list other languages need.
@dataclass(frozen=True)
class _Move:
    """Step one place along ``dim``; ``None`` means the current value."""

    dim: int | None
    delta: int


@dataclass(frozen=True)
class _SetValue:
    """Write a value into the addressed byte."""

    value: int


@dataclass(frozen=True)
class _AddValue:
    """Add to the addressed byte."""

    delta: int


@dataclass(frozen=True)
class _FromCoord:
    """Write a coordinate into the addressed byte, as a byte."""

    dim: int


@dataclass(frozen=True)
class _Clear:
    """Forget the position along ``dim``."""

    dim: int


type _Effect = _Move | _SetValue | _AddValue | _FromCoord | _Clear


@dataclass(frozen=True)
class _Context:
    """Everything one command's handler may read about the run.

    Bundles the run state ``_advance`` receives with the code, the
    bracket map, the tape views, and the value the shell read for one of
    the three reading commands, so each handler takes just this.
    """

    ind: int
    comment: bool
    axis: int
    code: str
    match: Mapping[int, int]
    value: Callable[[], int]
    coord: Callable[[int], int]
    port: int | None

    def at(
        self,
        ind: int | None = None,
        *,
        comment: bool | None = None,
        axis: int | None = None,
    ) -> _State:
        """Return the run state, with the given fields replaced."""
        return (
            self.ind if ind is None else ind,
            self.comment if comment is None else comment,
            self.axis if axis is None else axis,
        )


#: What a per-command handler returns: the next state and the tape effect.
type _Handler = Callable[[_Context], tuple[_State, _Effect | None]]


def _move_right(ctx: _Context) -> tuple[_State, _Effect | None]:
    """``>d``: step the axis pointer one place along dimension ``d``."""
    dim, ind = _number(ctx.code, ctx.ind, None)
    return (ctx.at(ind), _Move(dim, 1))


def _move_left(ctx: _Context) -> tuple[_State, _Effect | None]:
    """``<d``: step the axis pointer one place back along dimension ``d``."""
    dim, ind = _number(ctx.code, ctx.ind, None)
    return (ctx.at(ind), _Move(dim, -1))


def _increment(ctx: _Context) -> tuple[_State, _Effect | None]:
    """``+``: add one to the addressed byte."""
    return (ctx.at(), _AddValue(1))


def _decrement(ctx: _Context) -> tuple[_State, _Effect | None]:
    """``-``: subtract one from the addressed byte."""
    return (ctx.at(), _AddValue(-1))


def _print(ctx: _Context) -> tuple[_State, _Effect | None]:
    """``.``: no tape effect; the print already happened in the shell."""
    return (ctx.at(), None)


def _read_input(ctx: _Context) -> tuple[_State, _Effect | None]:
    """``,`` / ``d`` / ``x``: store the value the shell read."""
    return (ctx.at(), _SetValue(ctx.port if ctx.port is not None else 0))


def _char_literal(ctx: _Context) -> tuple[_State, _Effect | None]:
    """``:CH``: set the byte from the literal character that follows."""
    if ctx.ind >= len(ctx.code):
        raise syntax_error(
            "':' must be followed by a character",
            "follow : with one literal character, for example :A",
        )
    return (ctx.at(ctx.ind + 1), _SetValue(ord(ctx.code[ctx.ind])))


def _hex_literal(ctx: _Context) -> tuple[_State, _Effect | None]:
    """``=HEX``: set the byte from the two hex digits that follow."""
    if ctx.ind + 2 > len(ctx.code):
        raise syntax_error(
            "'=' must be followed by two hex digits",
            "follow = with exactly two hexadecimal digits, for example =41",
        )
    digits = ctx.code[ctx.ind : ctx.ind + 2]
    if any(char not in "0123456789abcdefABCDEF" for char in digits):
        raise syntax_error(
            f"invalid hex literal {digits!r}",
            "use hexadecimal digits 0-9 or A-F after =, for example =41",
        )
    return (ctx.at(ctx.ind + 2), _SetValue(int(digits, 16)))


def _select_axis(ctx: _Context) -> tuple[_State, _Effect | None]:
    """``$AXIS``: select which pointer the move and loop commands act on."""
    wanted, ind = _number(ctx.code, ctx.ind, 2)
    return (ctx.at(ind, axis=max(2, wanted)), None)


def _value_loop_open(ctx: _Context) -> tuple[_State, _Effect | None]:
    """``[``: skip past the matching ``]`` when the byte is zero."""
    if ctx.value() == 0:
        return (ctx.at(ctx.match[ctx.ind - 1] + 1), None)
    return (ctx.at(), None)


def _value_loop_close(ctx: _Context) -> tuple[_State, _Effect | None]:
    """``]``: return to just after the matching ``[``."""
    return (ctx.at(ctx.match[ctx.ind - 1]), None)


def _coord_loop_open(ctx: _Context) -> tuple[_State, _Effect | None]:
    """``{d``: skip past the matching ``}`` when the coordinate is zero."""
    open_i = ctx.ind - 1
    dim, ind = _number(ctx.code, ctx.ind, 0)
    if ctx.coord(dim) == 0:
        return (ctx.at(ctx.match[open_i] + 1), None)
    return (ctx.at(ind), None)


def _coord_loop_close(ctx: _Context) -> tuple[_State, _Effect | None]:
    """``}``: return to just after the matching ``{``."""
    return (ctx.at(ctx.match[ctx.ind - 1]), None)


def _coord_read(ctx: _Context) -> tuple[_State, _Effect | None]:
    """``?d``: write the dimension-``d`` coordinate into the byte."""
    dim, ind = _number(ctx.code, ctx.ind, 0)
    return (ctx.at(ind), _FromCoord(dim))


def _coord_clear(ctx: _Context) -> tuple[_State, _Effect | None]:
    """``!d``: clear the dimension-``d`` coordinate."""
    dim, ind = _number(ctx.code, ctx.ind, 0)
    return (ctx.at(ind), _Clear(dim))


#: Per-command handlers, keyed by the command character.  A character
#: absent here (and not ``*``) is not a command and is ignored.
_HANDLERS: dict[str, _Handler] = {
    ">": _move_right,
    "<": _move_left,
    "+": _increment,
    "-": _decrement,
    ".": _print,
    ",": _read_input,
    "d": _read_input,
    "x": _read_input,
    ":": _char_literal,
    "=": _hex_literal,
    "$": _select_axis,
    "[": _value_loop_open,
    "]": _value_loop_close,
    "{": _coord_loop_open,
    "}": _coord_loop_close,
    "?": _coord_read,
    "!": _coord_clear,
}


def _advance(
    state: _State,
    code: str,
    match: Mapping[int, int],
    value: Callable[[], int],
    coord: Callable[[int], int],
    port: int | None = None,
) -> tuple[_State, _Effect | None]:
    """Return the state after one command, and what it wants done.

    Pure: it reads its arguments and returns a description.  The tape is
    reached only through ``value`` and ``coord``, which the two loop forms
    need to place the cursor; the three reading commands arrive as ``port``.

    The cursor is already past the command; the caller advances it, since
    several commands can reject their operand (a ``:`` with nothing after
    it, a ``=`` without two hex digits) and the original had moved the
    cursor before looking.
    """
    ind, comment, axis = state
    c = code[ind - 1]

    if comment:
        return ((ind, c != "*", axis), None)
    if c == "*":
        return ((ind, True, axis), None)
    handler = _HANDLERS.get(c)
    if handler is None:
        # any other character is not a command and is ignored
        return ((ind, comment, axis), None)
    return handler(_Context(ind, comment, axis, code, match, value, coord, port))


class _Machine:
    """One Dimensional run: the code position, comment mode, and tape.

    The steppable machine, named as every other interpreter names it, so
    that the class carrying ``step``/``halted``/``snapshot`` is the one a
    reader finds by looking for ``_Machine``.  The pointer hierarchy it
    runs on is :class:`_Tape`.
    """

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.m = _matches(code)
        self.tape = _Tape()
        self.ind = 0
        self.comment = False

    @property
    def halted(self) -> bool:
        return self.ind >= len(self.code)

    # The VM's language-shaped view: Pointer hierarchy; ip is the code cursor, memory
    # the axes.

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [self.tape.peek_value()]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ind,
            self.comment,
            self.tape.axis,
            self.tape.top.level,
            self.tape.top.freeze(),
            self.io.progress(),
        )

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (self.ind, self.comment, self.tape.axis)

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields.

        The tape object itself never moves through the state, so only its
        axis is written back here; ``snapshot`` still reads the same tape
        it always did.
        """
        self.ind, self.comment, self.tape.axis = state

    def _apply(self, effect: _Effect) -> None:
        """Carry out the one tape change a command asked for."""
        tape = self.tape
        if isinstance(effect, _Move):
            dim = tape.value() if effect.dim is None else effect.dim
            tape.move(dim, effect.delta)
        elif isinstance(effect, _SetValue):
            tape.set_value(effect.value)
        elif isinstance(effect, _AddValue):
            tape.set_value(tape.value() + effect.delta)
        elif isinstance(effect, _FromCoord):
            tape.set_value(tape.coord(effect.dim) % 256)
        else:
            tape.clear(effect.dim)

    def step(self) -> None:
        """Execute one command (or comment character), advancing the position.

        The ports live here, not in the transition.  ``.`` prints the
        addressed byte; ``,``/``d``/``x`` read one as a character, a decimal
        number, and a hex number.

        The cursor advances before the command runs, since the original had
        moved it before rejecting a ``:`` at the end of the code, a ``=``
        without two hex digits, or any of the three reads at EOF.
        """
        if self.halted:
            return
        code = self.code
        c = code[self.ind]
        self.ind += 1

        port = None
        if not self.comment:
            if c == ".":
                self.io.print_char(chr(self.tape.value()))
            elif c == ",":
                port = self.io.input_char()
            elif c == "d":
                port = self.io.input_num()
            elif c == "x":
                port = int(self.io.input_token(), 16)

        state, effect = _advance(
            self._state, code, self.m, self.tape.value, self.tape.coord, port
        )
        self._restore(state)
        if effect is not None:
            self._apply(effect)


def run(code: str, io: IO) -> None:
    """Run a Dimensional v3.0 program."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
