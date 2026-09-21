"""Interpreter for Brainfuck.

8-bit wrapping tape growing rightward, ``<`` clamped at the left edge,
matching-bracket loops.  Unbalanced brackets raise :class:`ValueError`;
``,`` raises :class:`EOFError` on exhausted input (the spec leaves EOF
undefined), so ``,[.,]`` ends with an error.  :func:`_advance` is pure
over an immutable ``_State`` and ``snapshot`` returns it directly; the
shell does ``.`` and ``,``.  ``factor.py`` drives a decoded program through it.
"""

from __future__ import annotations

import sys
from functools import lru_cache

from esolangs.interpreters.brackets import match_brackets as matches
from esolangs.interpreters.io import IO

#: ``(ind, ptr, tape, acc, dirty)``: an immutable value, rebound per step.
#: ``acc`` is the true cell under the pointer; while ``dirty``, ``tape[ptr]``
#: is stale and :func:`_committed` (every path that leaves the cell) fixes it.
#: One rebuild per run of ``+``/``-`` instead of one per command: 58% of
#: executed commands are ``+``/``-``, in runs averaging 3.8, max 49.
#: ``snapshot`` and ``tape`` commit first, so one logical state has one
#: spelling and the cycle detector's hash sees a repeat as a repeat.
#: A plain tuple: ``NamedTuple.__new__`` is Python-level, 2.7x slower to
#: build, and this is built once per step.  Code and bracket map are
#: parameters, not fields, so the cycle detector stores no constants.
#: Order starts ``ind, ptr, tape`` because ``snapshot`` returns those three.
type _State = tuple[int, int, tuple[int, ...], int, bool]
type _Op = tuple[int, int]

_ADD = 0
_RIGHT = 1
_LEFT = 2
_OUTPUT = 3
_INPUT = 4
_OPEN = 5
_CLOSE = 6
_CLEAR = 7
_TRANSFER_RIGHT = 8


def _written(tape: tuple[int, ...], ptr: int, value: int) -> tuple[int, ...]:
    """Return ``tape`` with cell ``ptr`` set to ``value``.

    Affordable because the buffer means a run of ``+``/``-`` reaches this
    once, and a tape is the handful of cells touched (nine to eighteen).
    """
    return (*tape[:ptr], value, *tape[ptr + 1 :])


def _committed(state: _State) -> tuple[int, ...]:
    """Return ``state``'s tape with the buffered cell written back if stale.

    The one place the buffer's invariant is discharged.
    """
    _, ptr, tape, acc, dirty = state
    return _written(tape, ptr, acc) if dirty else tape


def _advance(state: _State, code: str, brackets: dict[int, int]) -> _State:
    """Return the state after executing the command at the code position.

    Pure; ``,``'s value arrives already written.  Fields are unpacked and one
    state built at the end: per-branch rebuilds made this ~5.6x slower than
    the mutable original, against ~2x.
    """
    ind, ptr, tape, acc, dirty = state
    char = code[ind]
    if char == "+":
        # Buffered; the tape is untouched.
        acc = (acc + 1) % 256
        dirty = True
    elif char == "-":
        acc = (acc - 1) % 256
        dirty = True
    elif char == ">":
        # Leaving the cell: commit first.  Past the right end grows by one.
        tape = _committed(state)
        dirty = False
        ptr += 1
        if ptr == len(tape):
            tape = (*tape, 0)
        acc = tape[ptr]
    elif char == "<":
        # Clamped at the left edge; a clamped move stays, so no commit.
        if ptr:
            tape = _committed(state)
            dirty = False
            ptr -= 1
            acc = tape[ptr]
    elif (char == "[" and acc == 0) or (char == "]" and acc != 0):
        # Tests ``acc`` (the truth).  Lands on the partner; +1 steps past it.
        ind = brackets[ind]
    return (ind + 1, ptr, tape, acc, dirty)


class _Machine:
    """A Brainfuck run: one immutable ``_State``, rebound per step."""

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.brackets = matches(code)
        # ``halted`` is read twice per command; take the length once.
        self.size = len(code)
        self.state: _State = (0, 0, (0,), 0, False)

    # Views for ``factor.py``.  ``tape`` and ``snapshot`` commit first: an
    # observer never sees the stale window (see ``_State``).

    @property
    def tape(self) -> tuple[int, ...]:
        return _committed(self.state)

    @property
    def ptr(self) -> int:
        return self.state[1]

    @property
    def ind(self) -> int:
        return self.state[0]

    def input_position(self) -> int:
        """Report the input cursor for the growth detector."""
        return self.io.position()

    @property
    def halted(self) -> bool:
        return self.state[0] >= self.size

    # VM view.  ``memory`` goes through ``tape``, so it commits too.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.tape)

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Committed tape plus input cursor (a repeat that ignores consumed
        # input is not a cycle).  ``acc``/``dirty`` would give one state two hashes.
        ind, ptr = self.state[0], self.state[1]
        return (ind, ptr, _committed(self.state), self.io.position())

    def step(self) -> None:
        """Execute one command, advancing the code position.

        The shell does ``.`` and ``,`` through the write buffer (``acc`` is the
        cell's true value).
        """
        state = self.state
        if state[0] >= self.size:
            return
        ind, ptr, tape, acc, _dirty = state
        char = self.code[ind]
        if char == ".":
            self.io.print_char(chr(acc))
        elif char == ",":
            # ``input_char`` is a whole code point.  Unreduced, ``,.`` echoed
            # an emoji while ``,+.`` printed ``\x01``.  CVNC does the same.
            state = (ind, ptr, tape, self.io.input_char() % 256, True)
        self.state = _advance(state, self.code, self.brackets)


@lru_cache(maxsize=16)
def _compile(code: str) -> tuple[_Op, ...]:
    """Return compact operations for the mutable run path."""
    brackets = matches(code)
    ops: list[_Op] = []
    op_at: dict[int, int] = {}
    ind = 0
    while ind < len(code):
        char = code[ind]
        if char in "+-":
            change = 0
            while ind < len(code) and code[ind] in "+-":
                change += 1 if code[ind] == "+" else -1
                ind += 1
            if change % 256:
                ops.append((_ADD, change % 256))
            continue
        if char in "><":
            end = ind + 1
            while end < len(code) and code[end] == char:
                end += 1
            ops.append((_RIGHT if char == ">" else _LEFT, end - ind))
            ind = end
            continue
        if char == "[" and code[ind : ind + 3] in ("[-]", "[+]"):
            ops.append((_CLEAR, 0))
            ind += 3
            continue
        if char == "[" and code[ind : ind + 2] == "[>":
            end = ind + 2
            change = 0
            while end < len(code) and code[end] in "+-":
                change += 1 if code[end] == "+" else -1
                end += 1
            if end > ind + 2 and code[end : end + 3] == "<-]":
                ops.append((_TRANSFER_RIGHT, change % 256))
                ind = end + 3
                continue
        if char in ".,[]":
            op_at[ind] = len(ops)
            opcode = {".": _OUTPUT, ",": _INPUT, "[": _OPEN, "]": _CLOSE}[char]
            ops.append((opcode, brackets.get(ind, 0)))
        ind += 1
    for at, (opcode, target) in enumerate(ops):
        if opcode in (_OPEN, _CLOSE):
            ops[at] = (opcode, op_at[target])
    return tuple(ops)


def run(code: str, io: IO) -> None:
    """Run compact operations over mutable local state."""
    ops = _compile(code)
    tape = bytearray(1)
    ptr = 0
    ind = 0
    output = io.print_char
    input_char = io.input_char
    while ind < len(ops):
        opcode, arg = ops[ind]
        if opcode == _ADD:
            tape[ptr] = (tape[ptr] + arg) % 256
        elif opcode == _RIGHT:
            ptr += arg
            if ptr >= len(tape):
                tape.extend(bytes(ptr + 1 - len(tape)))
        elif opcode == _LEFT:
            ptr = max(0, ptr - arg)
        elif opcode == _OUTPUT:
            output(chr(tape[ptr]))
        elif opcode == _INPUT:
            tape[ptr] = input_char() % 256
        elif (opcode == _OPEN and tape[ptr] == 0) or (
            opcode == _CLOSE and tape[ptr] != 0
        ):
            ind = arg
        elif opcode == _CLEAR:
            tape[ptr] = 0
        elif opcode == _TRANSFER_RIGHT:
            if ptr + 1 == len(tape):
                tape.append(0)
            tape[ptr + 1] = (tape[ptr + 1] + tape[ptr] * arg) % 256
            tape[ptr] = 0
        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
