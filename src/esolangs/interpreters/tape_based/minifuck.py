r"""Interpreter for Minifuck."""

import sys
from typing import NamedTuple

from esolangs.interpreters.io import IO

# : Width of the print window:.
_WIDTH = 8

# : Mask of the print window,.
_WINDOW = (1 << _WIDTH) - 1


class _State(NamedTuple):
    r"""An immutable Minifuck machine state."""

    code: str
    tape: int
    length: int
    ptr: int
    ind: int

    @property
    def halted(self) -> bool:
        r"""Whether the cursor has reached the end of the code."""
        return self.ind >= len(self.code)

    @property
    def cells(self) -> list[int]:
        r"""The tape as a list of bits, the shape callers and tests expect."""
        return [(self.tape >> i) & 1 for i in range(self.length)]


class _Effect(NamedTuple):
    r"""What a pure step owes the outside world: at most one IO action."""

    char: str | None = None
    reads: bool = False


# : The effect of a step that.
_QUIET = _Effect()


def _start(code: str) -> _State:
    r"""Return the initial state: an eight-cell tape at the origin."""
    return _State(code, 0, _WIDTH, 0, 0)


def _pool(tape: int) -> int:
    r"""Read cells 0-7 as one binary byte, cell 0 the most significant bit."""
    window = tape & _WINDOW
    return sum(
        ((window >> i) & 1) << (_WIDTH - 1 - i)  # .
        for i in range(_WIDTH)
    )


def _load(state: _State, byte: int) -> _State:
    r"""Splice ``byte`` into the print window, keeping the tape past it."""
    bits = sum(((byte >> (_WIDTH - 1 - i)) & 1) << i for i in range(_WIDTH))
    return state._replace(tape=(state.tape & ~_WINDOW) | bits)


def _step(
    ins: str, tape: int, length: int, ptr: int
) -> tuple[int, int, int, bool, str | None, bool]:
    r"""One instruction as plain scalars: the language, with no state."""
    if ins == "<":
        return (tape, length, ptr - 1 if ptr else ptr, False, None, False)
    if ins not in ".[":
        # Anything else is a comment.
        return (tape, length, ptr, False, None, False)

    # Both commands walk right and.
    # tape so the cell *after* the.
    # The appended cell is a zero,.
    # recorded length has to move.
    ptr += 1
    if ptr + 1 >= length:
        length += 1
    tape ^= 1 << ptr

    if ins == ".":
        # A non-zero window prints; a.
        # byte back through _load --.
        pool = _pool(tape)
        if pool:
            return (tape, length, ptr, False, chr(pool), False)
        return (tape, length, ptr, False, None, True)

    if not (tape >> ptr) & 1:
        # [ flipped the cell to 0: flip.
        # one instruction, on top of.
        tape ^= 1 << (ptr + 1)
        return (tape, length, ptr, True, None, False)

    return (tape, length, ptr, False, None, False)


def _advance(state: _State) -> tuple[_State, _Effect]:
    r"""Execute one instruction, returning the next state and its effect."""
    if state.halted:
        return state, _QUIET

    ins = state.code[state.ind]
    tape, length, ptr, skipped, char, reads = _step(
        ins, state.tape, state.length, state.ptr
    )

    # A collapsed ``[`` skips the.
    # every step makes.
    ind = state.ind + (2 if skipped else 1)

    if char is not None:
        return _State(state.code, tape, length, ptr, ind), _Effect(char=char)
    if reads:
        return _State(state.code, tape, length, ptr, ind), _Effect(reads=True)
    return _State(state.code, tape, length, ptr, ind), _QUIET


class _Machine:
    r"""Per-run Minifuck state: the tape, pointer, and code cursor."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Start with an eight-cell tape at the origin."""
        self.io = io
        self.state = _start(code)

    @property
    def tape(self) -> list[int]:
        r"""The tape as a list, the shape callers and tests expect."""
        return self.state.cells

    @property
    def ptr(self) -> int:
        return self.state.ptr

    @property
    def ind(self) -> int:
        return self.state.ind

    # The VM's language-shaped view.
    # cursor: ``ip`` is that.
    # stack.
    # sits with the machine that.
    # caller cannot reach back into.

    @property
    def ip(self) -> int:
        r"""The code cursor."""
        return self.state.ind

    @property
    def memory(self) -> list[int]:
        r"""The tape's cells."""
        return self.state.cells

    @property
    def stack(self) -> list[object]:
        r"""Minifuck has no stack."""
        return []

    @property
    def halted(self) -> bool:
        r"""Whether the cursor has reached the end of the code."""
        return self.state.halted

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        state = self.state
        return (state.tape, state.length, state.ptr, state.ind, self.io.position())

    def step(self) -> None:
        r"""Execute one instruction, advancing the cursor."""
        state, effect = _advance(self.state)
        if effect.char is not None:
            self.io.print_char(effect.char)
        elif effect.reads:
            state = _load(state, self.io.input_char())
        self.state = state


def run(code: str, io: IO) -> None:
    r"""Run a Minifuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
