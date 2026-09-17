"""Interpreter for Minifuck.

A binary tape: ``[`` flips the current bit and skips the next instruction
when it became 0, ``.`` prints cells 0-7 as a byte or *reads* one when
they are zero, ``<`` moves left.  Not implicitly looped (the talk page
leaves it open): the run halts at the end of the code.  Exhausted input
raises :class:`EOFError`.  :func:`_advance` is a pure function from
:class:`_State` to the next state plus an :class:`_Effect` naming what
the shell owes; :func:`_load` is the pure half of a read.
"""

import sys
from typing import NamedTuple

from esolangs.interpreters.io import IO

#: Width of the print window: ``.`` reads cells 0-7 as one binary byte.
_WIDTH = 8

#: Mask of the print window, cells 0-7.
_WINDOW = (1 << _WIDTH) - 1


class _State(NamedTuple):
    """An immutable Minifuck machine state.

    The tape is an ``int`` bitvector, cell *i* at bit *i*: a flip is
    ``tape ^ (1 << ptr)``, O(1) and immutable (a tuple rebuilt per flip was
    152x slower by tape 20000).  ``length`` is carried because trailing zeros
    are invisible in the int.
    """

    code: str
    tape: int
    length: int
    ptr: int
    ind: int

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.ind >= len(self.code)

    @property
    def cells(self) -> list[int]:
        """The tape as a list of bits, the shape callers and tests expect."""
        return [(self.tape >> i) & 1 for i in range(self.length)]


class _Effect(NamedTuple):
    """What a pure step owes the outside world: at most one IO action.

    ``char`` is the byte printed or ``None``; ``reads`` says the shell must
    fetch a byte for :func:`_load`.
    """

    char: str | None = None
    reads: bool = False


#: The effect of a step that does no IO, shared rather than rebuilt per step.
_QUIET = _Effect()


def _start(code: str) -> _State:
    """Return the initial state: an eight-cell tape at the origin."""
    return _State(code, 0, _WIDTH, 0, 0)


def _pool(tape: int) -> int:
    """Read cells 0-7 as one binary byte, cell 0 the most significant bit.

    The one place the tape's and the byte's orders meet.
    """
    window = tape & _WINDOW
    return sum(
        ((window >> i) & 1) << (_WIDTH - 1 - i)  #
        for i in range(_WIDTH)
    )


def _load(state: _State, byte: int) -> _State:
    """Splice ``byte`` into the print window, keeping the tape past it.

    The ``& ~_WINDOW`` is defensive (the window is already zero when this is
    called, 6016 calls checked); a mutant dropping it is equivalent, not a gap.
    """
    bits = sum(((byte >> (_WIDTH - 1 - i)) & 1) << i for i in range(_WIDTH))
    return state._replace(tape=(state.tape & ~_WINDOW) | bits)


def _step(
    ins: str, tape: int, length: int, ptr: int
) -> tuple[int, int, int, bool, str | None, bool]:
    """One instruction as plain scalars: the language, with no state objects.

    Returns ``(tape, length, ptr, skipped, char, reads)``.  The single
    definition: :func:`_advance` wraps it, and the boolean generator's
    emitter calls it directly (a state object per step measured 4.2x).
    """
    if ins == "<":
        return (tape, length, ptr - 1 if ptr else ptr, False, None, False)
    if ins not in ".[":
        # Anything else is a comment character: only the cursor moves.
        return (tape, length, ptr, False, None, False)

    # Both commands walk right and flip the cell they land on, growing the
    # tape so the cell *after* the pointer always exists for the skip below.
    # The appended cell is a zero, which the int already spells: only the
    # recorded length has to move.
    ptr += 1
    if ptr + 1 >= length:
        length += 1
    tape ^= 1 << ptr

    if ins == ".":
        # A non-zero window prints; a zero one reads, and the shell owes the
        # byte back through _load -- the decision is pure, the fetch is not.
        pool = _pool(tape)
        if pool:
            return (tape, length, ptr, False, chr(pool), False)
        return (tape, length, ptr, False, None, True)

    if not (tape >> ptr) & 1:
        # [ flipped the cell to 0: flip the one beyond it and skip ahead by
        # one instruction, on top of the advance every step makes.
        tape ^= 1 << (ptr + 1)
        return (tape, length, ptr, True, None, False)

    return (tape, length, ptr, False, None, False)


def _advance(state: _State) -> tuple[_State, _Effect]:
    """Execute one instruction, returning the next state and its effect.

    Pure; stepping a halted state is a no-op.
    """
    if state.halted:
        return state, _QUIET

    ins = state.code[state.ind]
    tape, length, ptr, skipped, char, reads = _step(
        ins, state.tape, state.length, state.ptr
    )

    # A collapsed ``[`` skips the next instruction, on top of the advance
    # every step makes.
    ind = state.ind + (2 if skipped else 1)

    if char is not None:
        return _State(state.code, tape, length, ptr, ind), _Effect(char=char)
    if reads:
        return _State(state.code, tape, length, ptr, ind), _Effect(reads=True)
    return _State(state.code, tape, length, ptr, ind), _QUIET


class _Machine:
    """Per-run Minifuck state: the tape, pointer, and code cursor.

    The tape never rewinds, so a program always halts.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Start with an eight-cell tape at the origin."""
        self.io = io
        self.state = _start(code)

    @property
    def tape(self) -> list[int]:
        """The tape as a list, the shape callers and tests expect."""
        return self.state.cells

    @property
    def ptr(self) -> int:
        return self.state.ptr

    @property
    def ind(self) -> int:
        return self.state.ind

    # The VM's language-shaped view.  Minifuck is a binary tape walked by a
    # cursor: ``ip`` is that cursor, ``memory`` the cells, and there is no
    # stack.  These live here rather than in ``esolangs.vm`` so the mapping
    # sits with the machine that knows it; the lists are fresh copies, so a
    # caller cannot reach back into the tape through them.

    @property
    def ip(self) -> int:
        """The code cursor."""
        return self.state.ind

    @property
    def memory(self) -> list[int]:
        """The tape's cells."""
        return self.state.cells

    @property
    def stack(self) -> list[object]:
        """Minifuck has no stack."""
        return []

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.state.halted

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        ``length`` rides along, since trailing zeros are invisible in the int.
        """
        state = self.state
        return (state.tape, state.length, state.ptr, state.ind, self.io.position())

    def step(self) -> None:
        """Execute one instruction, advancing the cursor."""
        state, effect = _advance(self.state)
        if effect.char is not None:
            self.io.print_char(effect.char)
        elif effect.reads:
            state = _load(state, self.io.input_char())
        self.state = state


def run(code: str, io: IO) -> None:
    """Run a Minifuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
