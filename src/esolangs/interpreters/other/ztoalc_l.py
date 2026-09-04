"""Interpreter for ZTOALC L.

Programs are a list of lines; line 1 holds the initial pointer.  Execution
visits line ``v`` when the Collatz step equals ``v``, halting when the value
reaches 1.  Commands print, jump, assign, add, and subtract using the current
value as an expression.

Expressions follow the wiki's grammar: ``input`` (read a character's ASCII
value), a variable, a number, ``[size]`` to create an array of ``size``
elements, and ``array[index]`` where ``array`` is any expression evaluating
to an array -- so nested indexing and arrays-of-arrays (an element that is
itself an array) are supported.  A command missing a required operand, an
empty or unbalanced index expression (``a[]``, ``a[1``), is a malformed
program and is rejected with :class:`ValueError`; referencing an undefined
variable, indexing out of range, reaching a negative pointer, or using an
array where a number is required are invalid operations that halt the
program with :class:`~esolangs.exceptions.HaltError`.

Exhausted input raises :class:`EOFError` (the repo-wide convention).

The interpreter runs on a :class:`_Machine` (the code, variables, and
Collatz pointer), so it is step-capable: ``step()`` executes the line at
the current pointer and advances it to the next line in the trajectory,
and ``halted`` is true once the pointer reaches 1.
"""

import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

Value = int | list["Value"]


def _is_int(tok: str) -> bool:
    """Whether ``tok`` is a decimal integer literal (possibly negative)."""
    return tok.lstrip("-").isdigit() and tok != "-"


def _as_int(value: Value) -> int:
    """Require ``value`` to be an integer, halting on an array."""
    if not isinstance(value, int):
        raise HaltError
    return value


def _freeze(value: Value) -> object:
    """Return a hashable form of ``value`` (arrays become nested tuples)."""
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


#: What a step decides to do, for the shell to carry out.  ``Print`` holds
#: the codepoint to write; ``Store`` names the variable, the index
#: expressions that walk into it, and the value to put there.
#:
#: The effects exist because a store has to reach the *live* list.  Two
#: names can share one array, so writing through a copy would lose the
#: other name's view of it -- and a value can even contain itself, which no
#: frozen form survives.
@dataclass(frozen=True)
class _Print:
    """Write one codepoint."""

    value: int


@dataclass(frozen=True)
class _Store:
    """Assign ``value`` to ``name`` walked through ``indexes``.

    The indexes are already evaluated.  They have to be: an index can read
    ``input``, and that read is part of the step's evaluation rather than
    of applying its result.
    """

    name: str
    indexes: tuple[int, ...]
    value: Value


type _Effect = _Print | _Store


@dataclass
class _State:
    """The changing Collatz pointer and alias-preserving variable heap."""

    ptr: int
    var: dict[str, Value]


#: The input port, injected by the shell.  ``input`` is an atom, so a line
#: may read several times partway through an expression, and the bytes are
#: taken *as the evaluation reaches them* -- a line that faults after one
#: read has consumed that byte, exactly as the original did.  Point Break
#: and Qoibl carry the same callback for the same reason.
type _Read = Callable[[], int]


def _no_read() -> int:
    """Refuse a read from a context that cannot hold an ``input`` atom."""
    raise AssertionError("a store target cannot read input")


def _atom(
    exp: str, pos: int, var: Mapping[str, Value], read: _Read
) -> tuple[Value, int]:
    """Parse the leading atom of ``exp`` from ``pos``.

    Returns ``(value, next_position)``.  An atom is ``[expr]`` (array
    creation), the ``input`` keyword, a number, or a variable name.
    """
    if not exp:
        raise ValueError("missing expression")
    if exp[pos] == "[":
        size, pos = _eval(exp, pos + 1, var, read)
        pos += 1  # the closing ']'
        return [0] * _as_int(size), pos
    j = pos
    while j < len(exp) and exp[j] not in "[]":
        j += 1
    tok = exp[pos:j]
    if tok == "input":
        return read(), j
    if _is_int(tok):
        return int(tok), j
    if tok in var:
        return var[tok], j
    raise HaltError


def _eval(
    exp: str, pos: int, var: Mapping[str, Value], read: _Read
) -> tuple[Value, int]:
    """Evaluate the expression ``exp`` from ``pos``, returning (value, pos).

    An expression is an atom followed by any number of ``[index]``
    indexings, so ``array[index]`` with a general ``array`` expression
    (including further indexings) works.
    """
    value, pos = _atom(exp, pos, var, read)
    while pos < len(exp) and exp[pos] == "[":
        index, pos = _eval(exp, pos + 1, var, read)
        pos += 1  # the closing ']'
        if not isinstance(value, list):
            raise HaltError
        i = _as_int(index)
        if i < 0 or i >= len(value):
            raise HaltError
        value = value[i]
    return value, pos


def _val(exp: str, var: Mapping[str, Value], read: _Read) -> Value:
    """Evaluate the expression ``exp``."""
    value, _ = _eval(exp, 0, var, read)
    return value


def _operand(lst: list[str], n: int) -> str:
    """Return the ``n``-th token of a command, rejecting a missing one."""
    if n >= len(lst):
        raise ValueError("missing operand in " + " ".join(lst))
    return lst[n]


def _split(lhs: str) -> tuple[str, list[str]]:
    """Split ``lhs`` into its base atom and index-expression strings."""
    atom = lhs[: lhs.find("[")]
    indexes: list[str] = []
    pos = lhs.find("[")
    while pos < len(lhs):
        depth = 1
        j = pos + 1
        while depth:
            if j >= len(lhs):
                raise ValueError(f"unbalanced brackets in {lhs!r}")
            if lhs[j] == "[":
                depth += 1
            elif lhs[j] == "]":
                depth -= 1
            j += 1
        indexes.append(lhs[pos + 1 : j - 1])
        pos = j
    return atom, indexes


def _next_ptr(ptr: int) -> int:
    """Return the next line in the Collatz trajectory of ``ptr``."""
    return 3 * ptr + 1 if ptr % 2 else ptr // 2


def _advance_line(
    ptr: int, code: list[str], var: Mapping[str, Value], read: _Read
) -> tuple[int, list[_Effect]]:
    """Return the next pointer and what the line under ``ptr`` wants done.

    Pure: it reads its arguments and returns a description.  Nothing is
    written and nothing is printed -- the caller does both, which is what
    lets a store reach the live arrays and keeps the aliasing the language
    has.

    ``read`` is the input port.  It is called as the evaluation reaches
    each ``input`` atom, so a line that faults part-way has consumed
    exactly the bytes to the left of the fault.

    A taken ``jump`` returns ``ptr + 1`` rather than the Collatz successor:
    it is the one line that chooses where to go.
    """
    p = ptr - 1
    if p < 0:
        raise HaltError
    ins = code[p] if p < len(code) else ""
    lst = ins.split()
    effects: list[_Effect] = []

    if not lst:
        pass
    elif lst[0] == "print":
        value = _as_int(_val(_operand(lst, 1), var, read))
        if not 0 <= value <= 0x10FFFF:
            raise HaltError
        effects.append(_Print(value))
    elif lst[0] == "jump":
        if _as_int(_val(_operand(lst, 2), var, read)):
            return (ptr + 1, effects)
    else:
        op = lst[1] if len(lst) > 1 else ""
        target = _operand(lst, 0)
        if op == "=":
            effects.append(
                _store_effect(target, _val(_operand(lst, 2), var, read), var, read)
            )
        elif op in ("+=", "+"):
            effects.append(
                _store_effect(
                    target,
                    _as_int(_val(target, var, read))
                    + _as_int(_val(_operand(lst, 2), var, read)),
                    var,
                    read,
                )
            )
        elif op in ("-=", "-"):
            effects.append(
                _store_effect(
                    target,
                    _as_int(_val(target, var, read))
                    - _as_int(_val(_operand(lst, 2), var, read)),
                    var,
                    read,
                )
            )

    return (_next_ptr(ptr), effects)


def _store_effect(
    lhs: str, value: Value, var: Mapping[str, Value], read: _Read
) -> _Store:
    """Describe an assignment to ``lhs``, evaluating its index path.

    The indexes are evaluated here rather than by the caller, because an
    index expression can contain ``input`` and that read happens while the
    step runs, not while its result is written.
    """
    if "[" not in lhs:
        return _Store(lhs, (), value)
    atom, indexes = _split(lhs)
    return _Store(
        atom,
        tuple(_as_int(_eval(idx, 0, var, read)[0]) for idx in indexes),
        value,
    )


class _Machine:
    """One ZTOALC L run: the code, variables, and Collatz pointer."""

    def __init__(self, code: list[str], io: IO) -> None:
        if not code:
            raise ValueError("ZTOALC L program cannot be empty")
        self.io = io
        self.code = code
        self.state = _State(int(code[0]), {})

    @property
    def ptr(self) -> int:
        """The current Collatz pointer."""
        return self.state.ptr

    @ptr.setter
    def ptr(self, ptr: int) -> None:
        self.state.ptr = ptr

    @property
    def var(self) -> dict[str, Value]:
        """The variable heap, including its live list aliases."""
        return self.state.var

    @property
    def halted(self) -> bool:
        """Whether the Collatz trajectory has reached 1."""
        return self.ptr == 1

    # The VM's language-shaped view: Collatz-trajectory pointer; memory is the sorted
    # variable values.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ptr

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [v for _, v in sorted(self.var.items()) if isinstance(v, int)]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ptr,
            tuple(sorted((k, _freeze(v)) for k, v in self.var.items())),
            self.io.position(),
        )

    def _apply(self, effect: _Effect) -> None:
        """Carry out one effect the core described.

        A store walks the live arrays and writes into the last one, which
        is what keeps two names sharing an array in step with each other.
        """
        if isinstance(effect, _Print):
            self.io.print_char(chr(effect.value))
            return
        if not effect.indexes:
            self.var[effect.name] = effect.value
            return
        # A store target names a variable, never ``input``, so the port
        # here can only be reached by a program shape that does not exist.
        target, _ = _atom(effect.name, 0, self.var, _no_read)
        for i in effect.indexes[:-1]:
            if not isinstance(target, list):
                raise HaltError
            if i < 0 or i >= len(target):
                raise HaltError
            target = target[i]
        if not isinstance(target, list):
            raise HaltError
        i = effect.indexes[-1]
        if i < 0 or i >= len(target):
            raise HaltError
        target[i] = effect.value

    def step(self) -> None:
        """Execute the line at ``ptr`` and advance to the next in trajectory.

        The input port is passed in rather than reached for: the core
        calls ``read`` as it meets each ``input`` atom, so the line runs
        once and a fault part-way leaves the bytes to its left consumed,
        as the original did.
        """
        if self.halted:
            return
        ptr, effects = _advance_line(self.ptr, self.code, self.var, self.io.input_char)
        for effect in effects:
            self._apply(effect)
        self.ptr = ptr


def run(code: list[str], io: IO) -> None:
    """Run a ZTOALC L program, following the Collatz trajectory of line 1."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
