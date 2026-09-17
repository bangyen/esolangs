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


def run(code: str, io: IO) -> None:
    """Run a Brainfuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
