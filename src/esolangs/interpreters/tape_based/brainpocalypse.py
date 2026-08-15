"""Interpreter for Brainpocalypse.

A brainfuck-like tape language with four commands: ``+``/``-`` increment/
decrement the current cell, ``>``/``<`` move the tape pointer, and ``-`` on
a zero cell rewinds the instruction pointer to the start of the program
(the wiki's flow-control rule, since cells never go negative).  Every other
character is ignored as a comment.  Cells hold nonnegative, unbounded
integers, and the tape is the wiki's default 256 cells wide, wrapping from
the start to the end (``>`` past cell 255 wraps to cell 0 and ``<`` at cell
0 wraps to cell 255).

The reference (``extra/assembly/brainpocalypse-riscv.s``) defines no I/O: the
program is read from stdin (there is no separate input channel) and, when
the program ends, the whole tape is printed as space-separated decimal
values — an output decision, not a language rule.  This interpreter mirrors
that: it takes the program as ``code`` and prints cells 0..n (where n is
the rightmost cell reached) through ``io``, and there is no input command.

Divergences from the reference (this interpreter follows the reference):
- cells are 32-bit dwords there but unbounded Python ints here, which is
  equivalent for any program the reference can complete;
- a NUL byte terminates the stored program in the reference, so ``code``
  is truncated at the first NUL.
"""

import sys

from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    """Run a Brainpocalypse program."""
    code = code.split("\x00", 1)[0]
    cells = dict.fromkeys(range(256), 0)
    ptr = 0
    right = 0
    ip = 0
    n = len(code)
    while True:
        while ip < n and code[ip] not in "+-><":
            ip += 1
        if ip == n:
            break
        c = code[ip]
        if c == "+":
            cells[ptr] += 1
        elif c == "-":
            if cells[ptr] == 0:
                ip = 0
                continue
            cells[ptr] -= 1
        elif c == ">":
            ptr = (ptr + 1) % 256
            if ptr > right:
                right = ptr
        else:  # "<"
            ptr = (ptr - 1) % 256
        ip += 1
    for i in range(right + 1):
        if i:
            io.print_str(" ")
        io.print_num(cells[i])


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
