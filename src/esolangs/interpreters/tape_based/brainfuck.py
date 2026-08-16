"""Interpreter for Brainfuck.

The semantics deliberately match the ASCII-art interpreter (which is
brainfuck with an art alphabet) so that the two are interchangeable: an
8-bit wrapping tape, rightward growth, ``<`` clamped at the left edge, and
matching-bracket loops.  This is what lets the BF-to-ASCII-art transpiler
be verified end-to-end.

The brainfuck spec defines ``[``/``]`` only for matched pairs; a program
with unbalanced brackets is malformed, so the interpreter rejects it with a
:class:`ValueError` rather than inventing a halt the language does not
specify.

The spec leaves EOF undefined for ``,`` (returning zero or leaving the cell
unchanged are both suggested); this interpreter instead raises
:class:`EOFError` when input is exhausted, so the classic `,[.,]` cat
program terminates with an error rather than a graceful halt.
"""

import sys

from esolangs.interpreters.brackets import match_brackets as matches
from esolangs.interpreters.io import IO


class _Machine:
    """A Brainfuck tape, its pointer, and the code position."""

    __slots__ = ("code", "io", "m", "tape", "ind", "ptr")

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.m = matches(code)
        self.tape: list[int] = [0]
        self.ind = 0
        self.ptr = 0

    @property
    def halted(self) -> bool:
        return self.ind >= len(self.code)

    def step(self) -> None:
        """Execute one command, advancing the code position."""
        char = self.code[self.ind]
        if char == ">":
            self.ptr += 1
            if self.ptr == len(self.tape):
                self.tape.append(0)
        elif char == "<" and self.ptr:
            self.ptr -= 1
        elif char == "+":
            self.tape[self.ptr] = (self.tape[self.ptr] + 1) % 256
        elif char == "-":
            self.tape[self.ptr] = (self.tape[self.ptr] - 1) % 256
        elif char == ".":
            self.io.print_char(chr(self.tape[self.ptr]))
        elif char == ",":
            self.tape[self.ptr] = self.io.input_char()
        elif (char == "[" and self.tape[self.ptr] == 0) or (
            char == "]" and self.tape[self.ptr] != 0
        ):
            self.ind = self.m[self.ind]

        self.ind += 1


def run(code: str, io: IO) -> None:
    """Run a Brainfuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
