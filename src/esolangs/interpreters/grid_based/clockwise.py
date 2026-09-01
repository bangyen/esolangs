"""Interpreter for Clockwise.

A pointer walks clockwise around a square ring, turning at R cells (or at ?
when the accumulator is nonzero, or ! when it is zero).  ; outputs the
accumulator parity, . reads an input bit, S zeroes the accumulator, and seven
parity bits are grouped into one printed byte.

The wiki defines the program as a closed ring; a pointer that walks off the
edge is a malformed program and is rejected with :class:`ValueError`.  Input
bits are read once at the start and then rotated, so a program that consumes
more than 7 bits re-reads them rather than halting on exhausted input.

Exhausted input raises :class:`EOFError` (the repo-wide convention).

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and the ring to the next state, and never
mutates what it is given.  It takes no ``io`` argument at all, so it is
total and side-effect free by construction rather than by inspection.

Input is not an effect during a run: the bits are read once in
``__init__`` and then rotated, so ``.`` consumes from a queue the state
carries rather than from the outside world.  That leaves ``step`` with one
effect -- flushing a byte once seven parity bits accumulate -- and one
error, the ``EOFError`` for a program that reads with no bits at all.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what Clockwise *does* stays in
the pure layer.
"""

from __future__ import annotations

import sys

from esolangs.interpreters.io import IO

#: How many parity bits make one printed byte.
_BYTE_BITS = 7

#: One instant of a run: ``(row, col, r, acc, out, inp, done)`` -- the
#: pointer's position and heading, the accumulator, the parity bits not yet
#: flushed, the rotating input bits, and whether the ring has closed.  A
#: value, not a record: every transition below returns a new one rather
#: than editing one in place, and both bit queues are tuples for the same
#: reason.
#:
#: ``done`` is state because halting here is a property of the *move*: the
#: pointer returning to the origin ends the run, except on a ``0`` heading,
#: so the position alone does not say whether the ring has closed.
#:
#: ``done`` stays out of ``snapshot``, which reports the six live fields
#: plus the input cursor, in the order it always returned them.
type _State = tuple[int, int, int, int, tuple[str, ...], tuple[str, ...], bool]

COL = [1, 0, -1, 0]
ROW = [0, 1, 0, -1]


def move(
    row: int,
    col: int,
    r: int,
    code: list[str],
    acc: int,
) -> tuple[int, int, int, str, int]:
    """Step the pointer one cell, returning position, direction, and the cell."""
    if not 0 <= row < len(code) or not 0 <= col < len(code[row]):
        raise ValueError("Clockwise ring is not closed")
    o = code[row][col]
    c = (o == "R") or (o == "?" and acc) or (o == "!" and not acc)

    r = (r + c) % 4
    row += ROW[r]
    col += COL[r]
    b = col or row or not r

    return row, col, r, o, b


def _advance(state: _State, code: list[str]) -> tuple[_State, int | None]:
    """Return the state after one cell, and any byte that is ready to print.

    Pure: it reads ``state`` and returns a new one.  The byte is reported
    rather than printed -- printing is the shell's -- and the seven bits
    are already cleared in the state that comes back.

    The move happens first: a cell's instruction is the one the pointer
    *left*, not the one it arrives on, which is what makes the ring walk
    and the instruction stream the same thing.

    A turn cell (``R``, or ``?``/``!`` when the accumulator agrees) needs
    no case of its own: the dispatch below has no branch for one, and a
    flush cannot fire on it -- ``out`` reaches seven only on the ``;`` that
    appends the seventh bit.  So a turn falls through to the shared
    ``cont`` check.

    A ``.`` on an empty queue is left for the shell to reject: bits are
    read up front, so an empty queue means the program was given none.
    """
    row, col, r, acc, out, inp, _done = state
    row, col, r, ins, cont = move(row, col, r, code, acc)

    if ins == "+":
        acc += 1
    elif ins == "-":
        acc -= 1
    elif ins == ".":
        # The queue rotates rather than draining, so a program that reads
        # more than seven bits re-reads them.
        acc = (acc | 1) - 1 + int(inp[0])
        inp = (*inp[1:], inp[0])
    elif ins == ";":
        out = (*out, str(acc % 2))
    elif ins == "S":
        acc = 0

    # The byte is reported whole rather than left in the state, because the
    # seventh bit is appended by *this* step -- a caller that read ``out``
    # beforehand would miss it, and one that read it afterwards would find
    # it already cleared.
    byte = None
    if len(out) == _BYTE_BITS:
        byte = int("".join(out), 2)
        out = ()
    return (row, col, r, acc, out, inp, not cont), byte


class _Machine:
    """Per-run Clockwise state: position, heading, accumulator, pending bits.

    ``step()`` moves the pointer one cell, executes its instruction, and
    flushes a printed byte when seven parity bits accumulate; ``halted`` is
    true once the pointer returns to the origin (a ``0`` heading is the only
    return that is *not* a halt, so a ring that re-enters the origin heading
    right loops forever).  The VM and the state-cycle hang detector expose
    this object.
    """

    def __init__(self, code: list[str], io: IO) -> None:
        """Pad ``code`` and read the input bits up front, like :func:`run`."""
        if not code:
            raise ValueError("Clockwise program cannot be empty")
        self.io = io
        size = max(len(lne) for lne in code)
        self.code = [c.ljust(size) for c in code]

        bits: list[str] = []
        if any("." in line for line in self.code):
            for k in io.input_str():
                val = f"{ord(k):07b}"
                bits += list(val.zfill(_BYTE_BITS))
        self.state: _State = (0, 0, 0, 0, (), tuple(bits), False)

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def row(self) -> int:
        return self.state[0]

    @property
    def col(self) -> int:
        return self.state[1]

    @property
    def r(self) -> int:
        return self.state[2]

    @property
    def acc(self) -> int:
        return self.state[3]

    @property
    def out(self) -> tuple[str, ...]:
        """The parity bits not yet flushed as a byte."""
        return self.state[4]

    @property
    def inp(self) -> tuple[str, ...]:
        """The input bits, which rotate rather than drain."""
        return self.state[5]

    @property
    def halted(self) -> bool:
        """Whether the pointer has returned to the origin."""
        return self.state[6]

    # The VM's language-shaped view: 2D ring; ip is the pointer's (row, col, heading),
    # memory the acc.

    @property
    def ip(self) -> tuple[int, ...]:
        """The current instruction position."""
        row, col, r = self.state[:3]
        return (row, col, r)

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [self.state[3]]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The six live fields plus the input cursor, in the order this
        # returned before ``done`` joined the state.
        row, col, r, acc, out, inp, _done = self.state
        return (row, col, r, acc, out, inp, self.io.position())

    def step(self) -> None:
        """Move the pointer one cell and execute the instruction it left.

        The byte flush and the empty-queue rejection live here rather than
        in the transition: this is the shell, so it is where an effect or a
        raise belongs.  The transition reports *that* a byte is ready and
        hands back a state with the bits already cleared, so this only has
        to write them.
        """
        if self.state[6]:
            return
        # Bits are read up front, so an empty queue means the program was
        # given none: reading one is exhausted input, which this module
        # documents as EOFError.  The cell about to run is the one the
        # pointer leaves, so the check has to look ahead the same way.
        if not self.state[5]:
            row, col, r, _acc, _out, _inp, _done = self.state
            if move(row, col, r, self.code, self.state[3])[3] == ".":
                raise EOFError
        self.state, byte = _advance(self.state, self.code)
        if byte is not None:
            self.io.print_char(chr(byte))


def run(code: list[str], io: IO) -> None:
    """Run a Clockwise program, reading input bits when the ring reads ``.``."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
