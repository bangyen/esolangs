r"""Interpreter for LaserFuck.

A laser (starting at ``o`` with a random initial heading) travels a grid.
``>``/``<``/``+``/``-``/``,`` work on a brainfuck-style tape, ``\`` and ``/``
reflect the laser, ``_``/``|`` and ``(``/``)`` reflect it when the current
cell is nonzero (or always for the unconditional forms), ``^v{}`` set the
heading directly, ``#`` skips the next command, ``x`` deletes the laser, and
``*`` duplicates it in a random perpendicular direction.  Execution ends when
no lasers remain; the tape is then printed, with the first grid cell ``\xff``
selecting byte mode (no separators) over the default decimal mode, and
negative cells excluded from the output.

The initial heading is chosen uniformly at random, matching the cross-check;
a run may therefore produce one of several outputs, so tests set a fixed
heading through :func:`run`.


Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import secrets
import sys

from esolangs.interpreters.io import IO


class _Machine:
    """A LaserFuck run: the grid, the live lasers, and the tape."""

    def __init__(self, code: list[str], io: IO, heading: int | None = None) -> None:
        self.io = io
        text = [list(ln) for ln in code]
        size = max(len(ln) for ln in text) if text else 0
        self.text = [ln + [" "] * (size - len(ln)) for ln in text]
        self.rows = len(text)

        self.ptr = 0
        self.tape: list[list[int]] = [[0, 0]]  # value, touched
        self.jmp = False
        self.ind = 0
        self.pos = (0, 0, 0)
        self._second_start = False

        self.lsrs: list[list[int]] = []
        for x, line in enumerate(self.text):
            for y, c in enumerate(line):
                if c == "o":
                    if self.lsrs:
                        self._second_start = True  # a second marker halts
                        return
                    # The random heading is part of LaserFuck's spec, not a
                    # secret.
                    d = heading if heading is not None else secrets.randbelow(4)
                    self.lsrs.append([x, y, d])
                    self.pos = (x, y, d)

    @property
    def halted(self) -> bool:
        return self._second_start or not self.lsrs

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ptr,
            tuple(tuple(cell) for cell in self.tape),
            self.jmp,
            self.ind,
            tuple(tuple(laser) for laser in self.lsrs),
            self.io.position(),
        )

    def step(self) -> None:
        """Move the active laser one step and execute the command it lands on."""
        if self.halted:
            return
        x, y, d = self.lsrs[self.ind]

        # move one step in the current direction
        if (x == 0 and d == 0) or (y == 0 and d == 2):
            x = self.rows  # step off the grid (top/left edges)
        elif d == 0:
            x -= 1
        elif d == 1:
            x += 1
        elif d == 2:
            y -= 1
        elif d == 3:
            y += 1

        self.pos = (x, y, d)

        if self.jmp:
            self.jmp = False
            self.lsrs[self.ind] = [x, y, d]
            self.ind = (self.ind + 1) % len(self.lsrs)
            return

        op = (
            self.text[x][y]
            if 0 <= x < self.rows and 0 <= y < len(self.text[0])
            else "x"
        )

        if op == ">":
            self.ptr += 1
            if self.ptr == len(self.tape):
                self.tape.append([0, 0])
        elif op == "<":
            if self.ptr > 0:
                self.ptr -= 1
            else:
                self.tape.insert(0, [0, 0])
        elif op == ",":
            line_val = self.io.input_str()
            # an empty (or blank) input line reads a zero, per the cross-check
            self.tape[self.ptr] = [ord(line_val[0]) if line_val else 0, 1]
        elif op == "x":
            self.lsrs.pop(self.ind)
            if self.lsrs:
                self.ind %= len(self.lsrs)
            return
        elif op == "*":
            self.lsrs.append([x, y, 2 * (1 - d // 2) + secrets.randbelow(2)])
        elif op in "_(":
            if d < 2 and (self.tape[self.ptr][0] != 0 or op == "_"):
                d = 1 - d
        elif op in "|)":
            if d > 1 and (self.tape[self.ptr][0] != 0 or op == "|"):
                d = 5 - d
        elif op == "/":
            d = 3 - d
        elif op in "^v{}":
            d = "^v{}".find(op)
        elif op == "\\":
            d = (d + 2) % 4
        elif op == "+":
            self.tape[self.ptr][0] += 1
            self.tape[self.ptr][1] = 1
        elif op == "-":
            self.tape[self.ptr][0] -= 1
            self.tape[self.ptr][1] = 1
        elif op == "#":
            self.jmp = True

        self.lsrs[self.ind] = [x, y, d]
        self.ind = (self.ind + 1) % len(self.lsrs)

    def dump(self) -> None:
        r"""Print the tape, honoring the ``\xff`` byte-mode marker."""
        out = bool(self.text) and bool(self.text[0]) and self.text[0][0] == "\u00ff"
        first = True
        for val, touched in self.tape:
            if touched and val >= 0:
                if out:
                    self.io.print_char(chr(val))
                elif first:
                    self.io.print_num(val)
                    first = False
                else:
                    self.io.print_line()
                    self.io.print_num(val)


def run(code: list[str], io: IO, heading: int | None = None) -> None:
    """Run a LaserFuck program, printing the tape when it halts.

    ``heading`` forces the laser's initial direction (0=up, 1=down, 2=left,
    3=right); when None it is drawn uniformly at random, matching the
    cross-check.
    """
    machine = _Machine(code, io, heading)
    while not machine.halted:
        machine.step()
    machine.dump()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.readlines(), IO())
