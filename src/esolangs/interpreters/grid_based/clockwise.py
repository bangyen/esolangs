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
"""

import sys

from esolangs.interpreters.io import IO

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
        self.row = self.col = self.r = 0
        self.acc = 0
        self.out: list[str] = []
        self.inp: list[str] = []
        self._done = False

        if "." in "".join(self.code):
            for k in io.input_str():
                val = f"{ord(k):07b}"
                self.inp += list(val.zfill(7))

    @property
    def halted(self) -> bool:
        """Whether the pointer has returned to the origin."""
        return self._done

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.row,
            self.col,
            self.r,
            self.acc,
            tuple(self.out),
            tuple(self.inp),
            self.io.position(),
        )

    def step(self) -> None:
        """Move the pointer one cell and execute the instruction it left."""
        if self._done:
            return
        row, col, r, ins, cont = move(self.row, self.col, self.r, self.code, self.acc)
        self.row, self.col, self.r = row, col, r

        if ins in "R?!":
            if not cont:
                self._done = True
            return

        if ins == "+":
            self.acc += 1
        elif ins == "-":
            self.acc -= 1
        elif ins == ".":
            n = int(self.inp[0])
            self.acc = (self.acc | 1) - 1 + n
            self.inp = [*self.inp[1:], self.inp[0]]
        elif ins == ";":
            self.out.append(str(self.acc % 2))
        elif ins == "S":
            self.acc = 0

        if len(self.out) == 7:
            char_val: int = int("".join(self.out), 2)
            self.io.print_char(chr(char_val))
            self.out = []

        if not cont:
            self._done = True


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
