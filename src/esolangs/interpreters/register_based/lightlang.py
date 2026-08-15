"""Lightlang interpreter implementation.

Esoteric language that uses only 1 bit as memory.
Each character is an instruction, invalid instructions are ignored.

Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import secrets
import sys
import time

from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    """Execute Lightlang code using a single bit of memory."""
    bit = ind = 0
    vel = 1

    while ind < len(code):
        sym = code[ind]
        if sym == "^":
            bit ^= 1
        elif sym == "!":
            io.print_num(bit)
        elif sym == "?":
            val = io.input_str()
            bit = (not val) + 0
        elif sym == "@":
            bit = secrets.randbelow(2)
        elif sym == "&" and bit:
            ind += vel
        elif sym == "#":
            return
        elif sym == "<":
            ind = -vel
        elif sym == "/":
            vel *= -1
        elif sym == "_":
            time.sleep(1)

        ind += vel


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
