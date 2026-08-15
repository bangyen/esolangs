"""Interpreter for Minifuck.

A binary tape where [ skips the next instruction when the flipped bit is 0
and . prints the first eight cells as a binary byte (reading a byte of input
instead when the pool is zero).  < moves the pointer left.

The program is not implicitly looped: execution halts when the instruction
pointer reaches the end of the code (the wiki talk page leaves the question
open; this interpreter does not assume an implicit loop).
"""

import sys

from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    """Run a Minifuck program."""
    tape: list[int] = [0] * 8
    ptr = ind = 0

    while ind < len(code):
        ins = code[ind]
        if ins == "<" and ptr:
            ptr -= 1
        elif ins in ".[":
            ptr += 1
            if ptr + 1 >= len(tape):
                tape.append(0)
            tape[ptr] ^= 1

            if ins == ".":
                lst = map(str, tape[:8])
                if n := int("".join(lst), 2):
                    io.print_char(chr(n))
                else:
                    val = f"{io.input_char():08b}"
                    tape = [*map(int, val), *tape[8:]]
            elif not tape[ptr]:
                tape[ptr + 1] ^= 1
                ind += 1

        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
