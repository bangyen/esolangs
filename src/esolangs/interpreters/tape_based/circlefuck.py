"""Interpreter for Circlefuck.

The tape is the program itself: cells wrap, + and - adjust the current cell,
, reads input, . outputs, [ and ] jump to matching brackets reading the cell,
@ halts, { and } insert and remove cells, and the pointer moves around the
circular tape.

A program with no instructions is malformed and is rejected with
:class:`ValueError`, as is one with unmatched ``[``/``]`` brackets; deleting
the last cell (``}``) is an invalid operation and halts the program with
:class:`~esolangs.exceptions.HaltError`.

Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import re
import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


def parse(code: str) -> list[int]:
    """Decode Circlefuck's escape sequences and keep printable commands only."""
    reg = r"\\(?:\d\d\d|" r"[\dA-F](?:$|[^\d]))"
    exp = r"((^|[^\\]) |\\( )|(\\)o)"

    for s in re.findall(reg, code):
        if len(s) == 4:
            val = oct(int(s[1:]))
            new = val[2:].zfill(3)
        else:
            new = f"x0{s[1:]}"
        code = code.replace(s, f"\\{new}")

    code = re.sub(exp, r"\2\3\4", code)
    code = "".join(c for c in code if 31 < ord(c) < 127)
    code = bytes(code, "utf-8").decode("unicode_escape")

    return [ord(c) for c in code]


def find(code: list[int], ind: int, ptr: int) -> int:
    """Return the matching bracket for ``ind``.

    Raises :class:`ValueError` if the brackets are unbalanced: the wiki
    defines ``[``/``]`` only for matched pairs, so an unmatched bracket is a
    malformed program.
    """
    char = chr(code[ind])
    if char == "[":
        if code[ptr]:
            return ind
        mode = 1
    else:
        if not code[ptr]:
            return ind
        mode = -1

    match = mode
    start = ind
    num = len(code)

    while match:
        ind = (ind + mode) % num
        sym = chr(code[ind])
        if ind == start:
            raise ValueError("unmatched bracket")
        if sym == "[":
            match += 1
        elif sym == "]":
            match -= 1
    return ind


class _Machine:
    """Per-run Circlefuck state: the tape (which is the program), and pointers.

    ``step()`` executes one cell and wraps the instruction pointer around the
    circular tape; ``halted`` is true once the pointer hits ``@``.  The tape
    and both pointers fully determine the next step, so a program that never
    halts is a finite-state cycle the hang detector can prove.  The VM and
    the hang detector expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code``; an empty program is malformed."""
        self.io = io
        self.cells: list[int] = parse(code)
        if not self.cells:
            raise ValueError("Circlefuck program cannot be empty")
        self.ind = 0
        self.ptr = 0
        self._done = False

    @property
    def halted(self) -> bool:
        """Whether the pointer hit ``@``."""
        return self._done

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (tuple(self.cells), self.ind, self.ptr, self.io.position())

    def step(self) -> None:
        """Execute one cell, advancing the pointers."""
        if self._done:
            return
        char = chr(self.cells[self.ind])
        if char == ">":
            self.ptr = (self.ptr + 1) % len(self.cells)
        elif char == "<":
            self.ptr = (self.ptr - 1) % len(self.cells)
        elif char == "+":
            self.cells[self.ptr] = (self.cells[self.ptr] + 1) % 256
        elif char == "-":
            self.cells[self.ptr] = (self.cells[self.ptr] - 1) % 256
        elif char == ",":
            self.cells[self.ptr] = self.io.input_char()
        elif char in "[]":
            self.ind = find(self.cells, self.ind, self.ptr)
        elif char == ".":
            self.io.print_char(chr(self.cells[self.ptr]))
        elif char == "@":
            self._done = True
            return
        elif char == "#":
            self.ind += 1
        elif char == "{":
            self.cells.insert(self.ptr, 0)
            self.ind += 1
        elif char == "}":
            if len(self.cells) == 1:
                raise HaltError
            self.cells.pop(self.ptr)
            self.ptr %= len(self.cells)

        self.ind = (self.ind + 1) % len(self.cells)


def run(code: str, io: IO) -> None:
    """Run a Circlefuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
