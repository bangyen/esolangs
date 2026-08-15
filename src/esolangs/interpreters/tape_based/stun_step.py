"""Interpreter for Stun Step.

A tape language with four commands: ``+``/``-`` increment and decrement the
current cell, and ``>``/``<`` move the pointer right and left -- but only
while the current cell is nonzero.  Cells are unbounded nonnegative integers,
initialized to 1 except the cell the pointer starts on, which is 0.  There is
no explicit flow control: once the program text is consumed, execution loops
back to the start unless the current cell is 0, in which case the machine
halts.  Decrementing a 0 cell is undefined per the wiki; this interpreter
leaves it at 0.

The wiki defines no I/O; on halting this interpreter prints the cells from
the leftmost through the rightmost position ever reached as space-separated
decimal values, so a run is observable (the same testing aid the repo's other
no-I/O languages use).
"""

import sys

from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    """Run a Stun Step program, printing the reached cells on halt."""
    tape: dict[int, int] = {0: 0}  # the current cell; everything else is 1
    ptr = 0
    left = right = 0
    while True:
        for c in code:
            if c == "+":
                tape[ptr] = tape.get(ptr, 1) + 1
            elif c == "-":
                tape[ptr] = max(0, tape.get(ptr, 1) - 1)
            elif c == ">" and tape.get(ptr, 1):
                ptr += 1
                if ptr > right:
                    right = ptr
            elif c == "<" and tape.get(ptr, 1):
                ptr -= 1
                if ptr < left:
                    left = ptr
        if tape.get(ptr, 1) == 0:
            break
    for k in range(left, right + 1):
        if k != left:
            io.print_str(" ")
        io.print_num(tape.get(k, 1))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
