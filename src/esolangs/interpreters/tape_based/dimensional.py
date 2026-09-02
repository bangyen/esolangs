"""Interpreter for Dimensional v3.0.

Dimensional v3.0 (the current wiki spec) is a hierarchy of pointers: an
``n``-pointer (n > 1) is an infinite-dimensional pointer whose position
contains an ``(n-1)``-slot, and a ``1``-slot holds an unsigned byte.  The
value is the byte reached by following the chain of pointers from the
selected axis down to level 2.  ``$AXIS`` picks which pointer the move and
loop commands act on; moving a higher pointer selects a fresh lower slot, so
moving away and back to the origin restores the previous tape.

The v3.0 wiki leaves some details open; this interpreter resolves them as
follows (documented choices, not part of any written spec):

* The pointer axis defaults to 2 (the innermost pointer, which addresses
  bytes directly), so ``>0``/``<0`` with no ``$AXIS`` is a linear byte tape.
* ``d`` and ``x`` read a decimal/hexadecimal number from input (like ``,``
  reads a character).
* ``$AXIS`` values below 2 are clamped to 2 (there is no 1-pointer).
* A ``:`` or ``=`` at the end of a program, or a malformed ``=`` literal, is
  a :class:`ValueError`; unmatched ``[``/``]`` or ``{``/``}`` brackets are
  rejected, matching the package's other tape interpreters.
* Cells wrap at 8 bits (unsigned bytes).

Commands: ``>d``/``<d`` move the axis pointer along dimension ``d`` (bare
``>``/``<`` use the value as the dimension), ``+``/``-`` adjust the value,
``:CH``/``=HEX`` set it from the source, ``.`` prints it, ``,``/``d``/``x``
read it from input, ``[``/``]`` loop on it, ``{d``/``}`` loop on the axis
pointer's dimension-``d`` coordinate, ``?d``/``!d`` read/clear it, ``$AXIS``
selects the pointer, and ``*`` toggles comment mode.

Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

from esolangs.interpreters.io import IO


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
    stack_b: list[int] = []
    stack_c: list[int] = []
    res: dict[int, int] = {}
    comment = False
    for i, char in enumerate(code):
        if comment:
            if char == "*":
                comment = False
            continue
        if char == "*":
            comment = True
        elif char == "[":
            stack_b.append(i)
        elif char == "]":
            if not stack_b:
                raise ValueError(f"unmatched ']' at position {i}")
            open_i = stack_b.pop()
            res[open_i] = i
            res[i] = open_i
        elif char == "{":
            stack_c.append(i)
        elif char == "}":
            if not stack_c:
                raise ValueError(f"unmatched '}}' at position {i}")
            open_i = stack_c.pop()
            res[open_i] = i
            res[i] = open_i
    if stack_b:
        raise ValueError(f"unmatched '[' at position {stack_b[-1]}")
    if stack_c:
        raise ValueError(f"unmatched '{{' at position {stack_c[-1]}")
    return res


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
#: for every command -- the cost that made A Painter Ant's tests 1300x
#: slower.  Nothing shares a level, so there is no aliasing to preserve
#: either: the transition names what it wants done to the tape and the
#: shell does it.
type _State = tuple[int, bool, int]


#: What a command wants done to the tape.  Every Dimensional command makes
#: at most one such change, so this is Minifuck's single-effect shape
#: rather than the list Eval and Painfuck need.
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


def _advance(
    state: _State,
    code: str,
    match: Mapping[int, int],
    value: Callable[[], int],
    coord: Callable[[int], int],
    port: int | None = None,
) -> tuple[_State, _Effect | None]:
    """Return the state after one command, and what it wants done.

    Pure in the sense the series means: it reads its arguments and returns
    a description.  The tape is reached only through ``value`` and
    ``coord``, which the two loop forms need to decide where the cursor
    goes, and the three reading commands arrive as ``port``.

    The cursor is already past the command.  Its advance is the caller's,
    because several commands can reject their operand -- a ``:`` with
    nothing after it, a ``=`` without two hex digits -- and the original
    had moved the cursor before it looked.
    """
    ind, comment, axis = state
    c = code[ind - 1]

    if comment:
        return ((ind, c != "*", axis), None)
    if c == "*":
        return ((ind, True, axis), None)
    if c == ">":
        dim, ind = _number(code, ind, None)
        return ((ind, comment, axis), _Move(dim, 1))
    if c == "<":
        dim, ind = _number(code, ind, None)
        return ((ind, comment, axis), _Move(dim, -1))
    if c == "+":
        return ((ind, comment, axis), _AddValue(1))
    if c == "-":
        return ((ind, comment, axis), _AddValue(-1))
    if c == ".":
        # The print already happened in the shell.
        return ((ind, comment, axis), None)
    if c in ",dx":
        return ((ind, comment, axis), _SetValue(port if port is not None else 0))
    if c == ":":
        if ind >= len(code):
            raise ValueError("':' must be followed by a character")
        return ((ind + 1, comment, axis), _SetValue(ord(code[ind])))
    if c == "=":
        if ind + 2 > len(code):
            raise ValueError("'=' must be followed by two hex digits")
        try:
            literal = int(code[ind : ind + 2], 16)
        except ValueError as exc:
            raise ValueError(f"invalid hex literal {code[ind : ind + 2]!r}") from exc
        return ((ind + 2, comment, axis), _SetValue(literal))
    if c == "$":
        wanted, ind = _number(code, ind, 2)
        return ((ind, comment, max(2, wanted if wanted is not None else 2)), None)
    if c == "[":
        if value() == 0:
            return ((match[ind - 1] + 1, comment, axis), None)
        return ((ind, comment, axis), None)
    if c == "]":
        return ((match[ind - 1], comment, axis), None)
    if c == "{":
        open_i = ind - 1
        dim, ind = _number(code, ind, 0)
        if coord(dim if dim is not None else 0) == 0:
            return ((match[open_i] + 1, comment, axis), None)
        return ((ind, comment, axis), None)
    if c == "}":
        return ((match[ind - 1], comment, axis), None)
    if c == "?":
        dim, ind = _number(code, ind, 0)
        return ((ind, comment, axis), _FromCoord(dim if dim is not None else 0))
    if c == "!":
        dim, ind = _number(code, ind, 0)
        return ((ind, comment, axis), _Clear(dim if dim is not None else 0))
    # any other character is not a command and is ignored
    return ((ind, comment, axis), None)


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
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [self.tape.value()]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ind,
            self.comment,
            self.tape.axis,
            self.tape.top.level,
            self.tape.top.freeze(),
            self.io.position(),
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

        The ports live here rather than in the transition: this is the
        shell.  ``.`` prints the addressed byte, and ``,``/``d``/``x`` read
        one -- as a character, a decimal number, and a hex number.

        The cursor is advanced before the command runs, because several
        commands reject their operand after the original had already moved
        it: a ``:`` at the end of the code, a ``=`` without two hex digits,
        and any of the three reads at EOF.
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
                port = int(self.io.input_str(), 16)

        state, effect = _advance(
            self._state, code, self.m, self.tape.value, self.tape.coord, port
        )
        self._restore(state)
        if effect is not None:
            self._apply(effect)


def run(code: str, io: IO) -> None:
    """Run a Dimensional v3.0 program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
