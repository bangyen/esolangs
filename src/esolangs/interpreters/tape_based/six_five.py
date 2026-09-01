"""Interpreter for 6-5.

The wiki spec is authoritative: ``7n`` skips the *next instruction* when the
cell equals ``n`` (the value is a parameter, never executed), and ``8n`` is a
two-character token that jumps to the n-th ``4`` marker.  To get this right
the program is tokenized first, merging each ``7``/``8`` with its operand,
rather than reading the next character on the fly.

Outputting a cell value outside the valid character range is an invalid
operation and halts the program with
:class:`~esolangs.exceptions.HaltError`.

Exhausted input raises :class:`EOFError` (the repo-wide convention).

The interpreter runs on a :class:`_Machine` (the token list, the cell, the
tape, and the cursor), so it is step-capable: ``step()`` executes one token
and ``halted`` is true once the cursor reaches the end of the program,
making a ``8n`` jump back to a ``4`` marker a finite-state cycle the state
cycle detector can prove.
"""

import re
import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


def num(char: str) -> int:
    """Decode a 6-5 operand digit: 0-9 literal, A-F hexadecimal."""
    if char.isdigit():
        return int(char)
    return ord(char.upper()) - 55


def _tokens(code: str) -> list[str]:
    """Split a program into instructions, merging each 7/8 with its operand.

    Comments start at a ``C`` that is not the operand of a ``7``/``8`` (a
    ``C`` after ``7``/``8`` is a value 12) and run to the end of the line.
    """
    code = re.sub(r"([^78])C[^\n]*", r"\1", code)
    toks: list[str] = []
    i = 0
    while i < len(code):
        if code[i] in "78" and i + 1 < len(code):
            toks.append(code[i : i + 2])
            i += 2
        else:
            toks.append(code[i])
            i += 1
    return toks


class _Machine:
    """Per-run 6-5 state: the tokens, cell, tape, and cursor.

    ``step()`` executes one token; ``halted`` is true once the cursor passes
    the last token.  A ``8n`` jump back to a ``4`` marker whose skip test
    never fires is a finite-state cycle the hang detector can prove.  The VM
    and the hang detector expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Tokenize ``code`` and reset the cell, tape, and cursor."""
        self.io = io
        self.toks = _tokens(code)
        self.cell = 0
        self.tape: list[int] = [0]
        self.ind = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has passed the last token."""
        return self.ind >= len(self.toks)

    # The VM's language-shaped view: Token tape + cursor; ip the cursor, memory the
    # cell tape.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.tape)

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.cell, tuple(self.tape), self.ind, self.io.position())

    def step(self) -> None:
        """Execute one token, advancing the cursor."""
        if self.halted:
            return
        tok = self.toks[self.ind]
        if tok == "1":
            self.cell += 2
            while len(self.tape) < self.cell + 1:
                self.tape.append(0)
        elif tok == "3" and self.cell:
            self.cell -= 1
        elif tok in ("5", "6"):
            self.tape[self.cell] += int(tok)
        elif tok in ("2", "9"):
            self.tape[self.cell] -= int(tok) % 6 + 3
        elif tok[0] == "8":
            val = num(tok[1]) if len(tok) > 1 else 0
            count = 0
            for j, t in enumerate(self.toks):
                if t == "4":
                    count += 1
                    if count == val:
                        self.ind = j
                        break
        elif tok[0] == "7":
            val = num(tok[1]) if len(tok) > 1 else 0
            if self.tape[self.cell] == val:
                self.ind += 1  # skip the next instruction
        elif tok == "0":
            self.ind = len(self.toks)  # halt
            return
        elif tok == "A":
            if not 0 <= self.tape[self.cell] <= 0x10FFFF:
                raise HaltError
            self.io.print_char(chr(self.tape[self.cell]))
        elif tok == "B":
            self.tape[self.cell] = self.io.input_char()

        self.ind += 1


def run(code: str, io: IO) -> None:
    """Run a 6-5 program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
