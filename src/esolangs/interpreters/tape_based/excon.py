"""Interpreter for EXCON.

An 8-cell bit pool with a pointer: : resets the pool and pointer, ^ flips the
current bit, < decrements the pointer, and ! prints the pool as a binary byte
(MSB first).  The language is straight-line with no control flow.

The wiki calls moving the pointer more than 8 steps left a fault; this
interpreter treats it as an invalid operation and halts the program with
:class:`~esolangs.exceptions.HaltError`.
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    """Run an EXCON program, printing each pool as a byte."""
    pool: list[int] = [0] * 8
    cell = 7

    for sym in code:
        if sym == ":":
            pool, cell = ([0] * 8, 7)
        elif sym == "^":
            pool[cell] ^= 1
        elif sym == "!":
            num = "".join(map(str, pool))
            io.print_char(chr(int(num, 2)))
        elif sym == "<":
            cell -= 1
            if cell < 0:
                raise HaltError


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
