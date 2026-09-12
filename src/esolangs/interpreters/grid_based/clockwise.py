r"""Interpreter for Clockwise."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from esolangs.exceptions import InputExhaustedError
from esolangs.interpreters.io import IO

# : How many parity bits make.
_BYTE_BITS = 7

# : One instant of a run:.
# : pointer's position and.
# : flushed, the rotating input.
# : value, not a record: every.
# : than editing one in place,.
#: reason.
# :.
# : ``done`` is state because.
# : pointer returning to the.
# : so the position alone does.
# :.
# : ``done`` stays out of.
# : plus the input cursor, in.
type _State = tuple[int, int, int, int, tuple[str, ...], tuple[str, ...], bool]

COL = [1, 0, -1, 0]
ROW = [0, 1, 0, -1]


def move(
    row: int,
    col: int,
    r: int,
    code: Sequence[str],
    acc: int,
) -> tuple[int, int, int, str, int]:
    r"""Step the pointer one cell, returning position, direction, and the."""
    if not 0 <= row < len(code) or not 0 <= col < len(code[row]):
        raise ValueError("Clockwise ring is not closed")
    o = code[row][col]
    c = (o == "R") or (o == "?" and acc) or (o == "!" and not acc)

    r = (r + c) % 4
    row += ROW[r]
    col += COL[r]
    b = col or row or not r

    return row, col, r, o, b


def _advance(state: _State, code: Sequence[str]) -> tuple[_State, int | None]:
    r"""Return the state after one cell, and any byte that is ready to."""
    row, col, r, acc, out, inp, _done = state
    row, col, r, ins, cont = move(row, col, r, code, acc)

    if ins == "+":
        acc += 1
    elif ins == "-":
        acc -= 1
    elif ins == ".":
        # The queue rotates rather than.
        # more than seven bits re-reads.
        acc = (acc | 1) - 1 + int(inp[0])
        inp = (*inp[1:], inp[0])
    elif ins == ";":
        out = (*out, str(acc % 2))
    elif ins == "S":
        acc = 0

    # The byte is reported whole.
    # seventh bit is appended by.
    # beforehand would miss it, and.
    # it already cleared.
    byte = None
    if len(out) == _BYTE_BITS:
        byte = int("".join(out), 2)
        out = ()
    return (row, col, r, acc, out, inp, not cont), byte


class _Machine:
    r"""Per-run Clockwise state: position, heading, accumulator, pending."""

    def __init__(self, code: list[str], io: IO) -> None:
        r"""Pad ``code`` and read the input bits up front, like :func:`run`."""
        if not code:
            raise ValueError("Clockwise program cannot be empty")
        self.io = io
        size = max(len(lne) for lne in code)
        self.code = tuple(c.ljust(size) for c in code)

        bits: list[str] = []
        if any("." in line for line in self.code):
            for k in io.input_str():
                val = f"{ord(k):07b}"
                bits += list(val.zfill(_BYTE_BITS))
        self.state: _State = (0, 0, 0, 0, (), tuple(bits), False)

    # The language's own names.
    # than fields of their own, so.

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
        r"""The parity bits not yet flushed as a byte."""
        return self.state[4]

    @property
    def inp(self) -> tuple[str, ...]:
        r"""The input bits, which rotate rather than drain."""
        return self.state[5]

    @property
    def halted(self) -> bool:
        r"""Whether the pointer has returned to the origin."""
        return self.state[6]

    # The VM's language-shaped.
    # memory the acc.

    # : ``ip`` is a cell of the.
    # : parts are a row and a.
    # : this a caller cannot tell.
    # : stack, which look identical.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...]:
        r"""The current instruction position."""
        row, col, r = self.state[:3]
        return (row, col, r)

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return [self.state[3]]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # The six live fields plus the.
        # returned before ``done``.
        row, col, r, acc, out, inp, _done = self.state
        return (row, col, r, acc, out, inp, self.io.position())

    def step(self) -> None:
        r"""Move the pointer one cell and execute the instruction it left."""
        if self.state[6]:
            return
        # Bits are read up front, so an.
        # given none: reading one is.
        # documents as EOFError.
        # pointer leaves, so the check.
        if not self.state[5]:
            row, col, r, _acc, _out, _inp, _done = self.state
            if move(row, col, r, self.code, self.state[3])[3] == ".":
                # ``InputExhaustedError``, not.
                # one (that is the class's.
                # carried no message and was.
                # sweep written to the.
                # crashed on this one language.
                # *empty* stdin has always.
                # ``ScriptedIO``; only this.
                # The counts come off the io by.
                # runs against the base ``IO``.
                raise InputExhaustedError(
                    getattr(self.io, "reads", 0), getattr(self.io, "supplied", 0)
                )
        self.state, byte = _advance(self.state, self.code)
        if byte is not None:
            self.io.print_char(chr(byte))


def run(code: list[str], io: IO) -> None:
    r"""Run a Clockwise program, reading input bits when the ring reads."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
