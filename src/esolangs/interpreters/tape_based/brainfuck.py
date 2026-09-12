r"""Interpreter for Brainfuck."""

from __future__ import annotations

import sys

from esolangs.interpreters.brackets import match_brackets as matches
from esolangs.interpreters.io import IO

# : One instant of a run:.
# : position, the pointer, the.
# : the pointer.
# : one rather than editing one.
#: same reason.
# :.
# : ``acc`` always holds the.
# : ``dirty`` is set,.
# : tape is brought back up to.
# : that leaves the cell goes.
# : ``-`` cost one tape rebuild.
# : commands real generated.
# : averaging 3.8 and reaching.
# :.
# : The stale window is.
# : property both commit first,.
# : tape.
# : ``snapshot`` returns, and a.
# : committed) would make a.
# :.
# : A plain tuple rather than a.
# : unpacking in the functions.
# : ``NamedTuple.__new__`` is.
# : C-level -- measured 2.7x.
# :.
# : The code and its bracket.
# : changes during a run, so.
# : value the cycle detector.
#: functions instead.
# :.
# : The field order starts.
# : ``snapshot`` returns, and.
# : buffer existed.
type _State = tuple[int, int, tuple[int, ...], int, bool]


def _written(tape: tuple[int, ...], ptr: int, value: int) -> tuple[int, ...]:
    r"""Return ``tape`` with cell ``ptr`` set to ``value``."""
    return (*tape[:ptr], value, *tape[ptr + 1 :])


def _committed(state: _State) -> tuple[int, ...]:
    r"""Return ``state``'s tape with the buffered cell written back if."""
    _, ptr, tape, acc, dirty = state
    return _written(tape, ptr, acc) if dirty else tape


def _advance(state: _State, code: str, brackets: dict[int, int]) -> _State:
    r"""Return the state after executing the command at the code position."""
    ind, ptr, tape, acc, dirty = state
    char = code[ind]
    if char == "+":
        # The buffered cell absorbs the.
        acc = (acc + 1) % 256
        dirty = True
    elif char == "-":
        acc = (acc - 1) % 256
        dirty = True
    elif char == ">":
        # Leaving the cell, so the.
        # the right end grows the tape.
        tape = _committed(state)
        dirty = False
        ptr += 1
        if ptr == len(tape):
            tape = (*tape, 0)
        acc = tape[ptr]
    elif char == "<":
        # ``<`` at the left edge is.
        # clamped move never leaves the.
        if ptr:
            tape = _committed(state)
            dirty = False
            ptr -= 1
            acc = tape[ptr]
    elif (char == "[" and acc == 0) or (char == "]" and acc != 0):
        # The test reads the buffer,.
        # or not the tape has caught up.
        # the test inverted, and the.
        # increment below steps past it.
        ind = brackets[ind]
    return (ind + 1, ptr, tape, acc, dirty)


class _Machine:
    r"""A Brainfuck run: one immutable ``_State``, rebound per step."""

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.brackets = matches(code)
        # ``halted`` is read twice per.
        # once by ``step``'s guard --.
        # rather than recomputed on.
        self.size = len(code)
        self.state: _State = (0, 0, (0,), 0, False)

    # The language's own names,.
    # on the current state rather.
    # place a step can change.
    # .
    # ``tape`` and ``snapshot``.
    # An observer must never see.
    # one the program has actually.
    # detector hashes snapshots --.
    # spelling, or a real repeat.

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
        r"""Report the input cursor for the growth detector."""
        return self.io.position()

    @property
    def halted(self) -> bool:
        return self.state[0] >= self.size

    # The VM's language-shaped.
    # tape.
    # buffer like every other.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return list(self.tape)

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # The committed tape, not the.
        # repeat that ignores consumed.
        # and ``dirty`` are.
        # representation of the tape,.
        # them would give one logical.
        ind, ptr = self.state[0], self.state[1]
        return (ind, ptr, _committed(self.state), self.io.position())

    def step(self) -> None:
        r"""Execute one command, advancing the code position."""
        state = self.state
        if state[0] >= self.size:
            return
        ind, ptr, tape, acc, _dirty = state
        char = self.code[ind]
        if char == ".":
            self.io.print_char(chr(acc))
        elif char == ",":
            # Reduced, like every other.
            # returns a whole code point,.
            # U+00FF used to put that code.
            # 8-bit tape: ``,.``.
            # 128512.
            # unreduced until arithmetic.
            # emoji while ``,+.`` printed.
            # ``(byte or 0) % 256`` for.
            state = (ind, ptr, tape, self.io.input_char() % 256, True)
        self.state = _advance(state, self.code, self.brackets)


def run(code: str, io: IO) -> None:
    r"""Run a Brainfuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
