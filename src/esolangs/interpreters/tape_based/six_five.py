"""Interpreter for 6-5.

The wiki spec is authoritative: ``7n`` skips the *next instruction* when the
cell equals ``n`` (the value is a parameter, never executed), and ``8n`` is a
two-character token that jumps to the n-th ``4`` marker.  To get this right
the program is tokenized first, merging each ``7``/``8`` with its operand,
rather than reading the next character on the fly.

Outputting a cell value outside the valid character range is an invalid
operation and halts the program with
:class:`~esolangs.exceptions.HaltError`.
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


def run(code: str, io: IO) -> None:
    """Run a 6-5 program."""
    toks = _tokens(code)
    cell = ind = 0
    tape: list[int] = [0]

    while ind < len(toks):
        tok = toks[ind]
        if tok == "1":
            cell += 2
            while len(tape) < cell + 1:
                tape.append(0)
        elif tok == "3" and cell:
            cell -= 1
        elif tok in ("5", "6"):
            tape[cell] += int(tok)
        elif tok in ("2", "9"):
            tape[cell] -= int(tok) % 6 + 3
        elif tok[0] == "8":
            val = num(tok[1]) if len(tok) > 1 else 0
            count = 0
            for j, t in enumerate(toks):
                if t == "4":
                    count += 1
                    if count == val:
                        ind = j
                        break
        elif tok[0] == "7":
            val = num(tok[1]) if len(tok) > 1 else 0
            if tape[cell] == val:
                ind += 1  # skip the next instruction
        elif tok == "0":
            return
        elif tok == "A":
            if not 0 <= tape[cell] <= 0x10FFFF:
                raise HaltError
            io.print_char(chr(tape[cell]))
        elif tok == "B":
            tape[cell] = io.input_char()

        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
