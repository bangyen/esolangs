"""Interpreter for Clockwise.

A pointer walks clockwise around a square ring, turning a quarter at
``R`` and at ``!`` when the accumulator is zero; ``?`` turns one quarter
when the accumulator is nonzero.  ``;`` outputs the
accumulator parity (seven bits per printed byte), ``.`` reads an input
bit, ``S`` zeroes.  Walking off the edge is malformed
(:class:`ValueError`): the page names no wrap, only the halt on
returning "to the northwesternmost character".  Input bits are read
once in ``__init__`` and then rotated, so ``.`` consumes from a queue in
the state; a program that reads with no bits at all raises
:class:`EOFError`.

Input characters form the initial bit queue. This implementation preserves the
complete supplied character stream rather than discarding later lines.
"""

from __future__ import annotations

from collections.abc import Sequence

from esolangs.exceptions import InputExhaustedError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

#: How many parity bits make one printed byte.
_BYTE_BITS = 7

#: ``(row, col, r, acc, out, inp)``: position, heading, accumulator,
#: unflushed parity bits, rotating input bits.  The ring closing is not a
#: field: the origin is re-entered only heading left or up, so being there
#: with ``r != 0`` is the end, and ``r == 0`` there is the start.
type _State = tuple[int, int, int, int, tuple[str, ...], tuple[str, ...]]

COL = [1, 0, -1, 0]
ROW = [0, 1, 0, -1]


def move(
    row: int,
    col: int,
    r: int,
    code: Sequence[str],
    acc: int,
) -> tuple[int, int, int, str]:
    """Step the pointer one cell, returning position, direction, and the cell."""
    if not 0 <= row < len(code) or not 0 <= col < len(code[row]):
        raise syntax_error(
            "Clockwise ring is not closed",
            (
                "place R turns so the pointer stays within the grid and "
                "returns to the origin"
            ),
        )
    o = code[row][col]
    c = (o == "R") or (o == "?" and acc != 0) or (o == "!" and acc == 0)

    r = (r + c) % 4
    return row + ROW[r], col + COL[r], r, o


# :func:`_advance` is a pure transition over an immutable ``_State`` with no ``io``
# argument; :class:`_Machine` rebinds one state per ``step()`` and flushes the byte.
def _advance(state: _State, code: Sequence[str]) -> tuple[_State, int | None]:
    """Return the state after one cell, and any byte that is ready to print.

    The move happens first: a cell's instruction is the one the pointer
    *left*.  A turn cell needs no case: no flush can fire on it, so it
    falls through to the shared flush check.  ``.`` on an empty queue is
    left for the shell to reject.
    """
    row, col, r, acc, out, inp = state
    row, col, r, ins = move(row, col, r, code, acc)

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
    return (row, col, r, acc, out, inp), byte


class _Machine:
    """Per-run Clockwise state: position, heading, accumulator, pending bits.

    ``halted`` is true once the pointer returns to the origin; the ``0``
    heading arm there is a guard, since :func:`move` refuses ``(0, -1)``.
    """

    def __init__(self, code: list[str], io: IO) -> None:
        """Pad ``code`` and read the input bits up front, like :func:`run`."""
        if not code:
            raise syntax_error(
                "Clockwise program cannot be empty",
                "provide a nonempty ring of cells with R turns at its corners",
            )
        self.io = io
        size = max(len(lne) for lne in code)
        self.code = tuple(c.ljust(size) for c in code)

        bits: list[str] = []
        if any("." in line for line in self.code):
            for k in io.input_all():
                bits += format(ord(k), f"0{_BYTE_BITS}b")
        self.state: _State = (0, 0, 0, 0, (), tuple(bits))

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
        row, col, r = self.state[:3]
        return row == col == 0 and r != 0

    # The VM's language-shaped view: 2D ring; ip is the pointer's (row, col, heading),
    # memory the acc.

    #: ``ip`` is a cell of the program's own rectangle: the first two
    #: parts are a row and a column, and the rest is a heading.  Without
    #: this a caller cannot tell the pair from a call depth or a frame
    #: stack, which look identical and mean somewhere else entirely.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...]:
        """The current instruction position."""
        row, col, r = self.state[:3]
        return (row, col, r)

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [self.state[3]]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*self.state, self.io.progress())

    def step(self) -> None:
        """Move the pointer one cell and execute the instruction it left."""
        if self.halted:
            return
        # Bits are read up front, so an empty queue means the program was
        # given none: reading one is exhausted input, which this module
        # documents as EOFError.  The cell about to run is the one the
        # pointer leaves, so the check has to look ahead the same way.
        if not self.state[5]:
            row, col, r, acc, _out, _inp = self.state
            if move(row, col, r, self.code, acc)[3] == ".":
                # ``InputExhaustedError`` (an ``EOFError`` too), not the
                # bare one: a sweep on ``except EsolangError`` crashed here.
                # Bits, not lines: the input was read up front as
                # characters, so the failed read is the first and the
                # supply is the character cursor.
                raise InputExhaustedError(0, self.io.position(), "character")
        self.state, byte = _advance(self.state, self.code)
        if byte is not None:
            self.io.print_char(chr(byte))


def run(code: list[str], io: IO) -> None:
    """Run a Clockwise program, reading input bits when the ring reads ``.``."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run, shape="keep")
