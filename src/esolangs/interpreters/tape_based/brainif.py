"""Interpreter for BrainIf.

Line-based: each ``if <value> <command>`` runs only when the cell equals
<value>.  Commands increment, move right/left, goto a line, read a byte of
input, or output the current cell.

A command line missing its required operands (``if`` without a value, or
``goto`` without a target) is a malformed program and is rejected with
:class:`ValueError`.

Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import sys

from esolangs.interpreters.io import IO


class _Machine:
    """Per-run BrainIf state: the cells, the line cursor, and the pointer.

    ``step()`` executes one line; ``halted`` is true once the cursor passes
    the last line.  A ``goto`` can rewind the cursor, so a loop whose cell
    never leaves the tested value is a finite-state cycle the state-cycle
    hang detector can prove.  The VM and the hang detector expose this
    object.
    """

    def __init__(self, code: list[str], io: IO) -> None:
        """Start with a single zero cell at the origin."""
        self.io = io
        self.code = code
        self.cells: list[int] = [0]
        self.ind = 0
        self.ptr = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has passed the last line."""
        return self.ind >= len(self.code)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (tuple(self.cells), self.ind, self.ptr, self.io.position())

    def step(self) -> None:
        """Execute one line, advancing the cursor."""
        if self.halted:
            return
        line = self.code[self.ind].strip()
        arr = line.split()

        if not line:
            self.ind += 1
            return
        if len(arr) < 2:
            raise ValueError("malformed BrainIf line: " + line)
        if self.cells[self.ptr] == int(arr[1]):
            if "inc" in line:
                self.cells[self.ptr] += 1
            elif "right" in line:
                self.ptr += 1
                if self.ptr == len(self.cells):
                    self.cells.append(0)
            elif "left" in line:
                self.ptr = max(0, self.ptr - 1)
            elif "goto" in line:
                if len(arr) < 4:
                    raise ValueError("goto requires a target line")
                self.ind = int(arr[3]) - 2
            elif "input" in line:
                s = ""

                while not s:
                    s = self.io.input_str()

                self.cells[self.ptr] = ord(s[0])
            elif "output" in line:
                self.io.print_char(chr(self.cells[self.ptr]))

        self.ind += 1


def run(code: list[str], io: IO) -> None:
    """Run a BrainIf program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
