"""Interpreter for NoComment.

The full wiki language (not a subset): a byte tape with a movable pointer,
plus a byte stack.  ``i``/``d`` increment/decrement the current cell, ``c``
clears it, ``l``/``r`` move the pointer (``l`` is a no-op at cell 0, ``r``
extends the tape), ``n`` pushes the current cell onto the stack, ``f`` pops
the stack into the current cell, ``s``/``b`` jump forward/backward by a
peeked stack value when the current cell is nonzero (``s`` skips X
instructions, ``b`` jumps back X-1), and ``o`` prints the current cell as a
byte.

Per the wiki, any character that is not a command is an error (there are no
comments), and popping an empty stack is an error.  A malformed program
(unrecognized character) raises :class:`ValueError`; an invalid operation
(stack underflow) raises :class:`~esolangs.exceptions.HaltError`.
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_COMMANDS = "idclrnfsbo"


def run(code: str, io: IO) -> None:
    """Run a NoComment program."""
    tape: list[int] = [0]
    stack: list[int] = []
    ptr = 0
    ind = 0

    while ind < len(code):
        c = code[ind]
        if c == "i":
            tape[ptr] = (tape[ptr] + 1) % 256
        elif c == "d":
            tape[ptr] = (tape[ptr] - 1) % 256
        elif c == "c":
            tape[ptr] = 0
        elif c == "l":
            if ptr:
                ptr -= 1
        elif c == "r":
            ptr += 1
            if ptr == len(tape):
                tape.append(0)
        elif c == "n":
            stack.append(tape[ptr])
        elif c == "f":
            if not stack:
                raise HaltError
            tape[ptr] = stack.pop()
        elif c == "s":
            if tape[ptr] and stack:
                # skip X forward: the next command is at ind + X + 1
                target = ind + stack[-1] + 1
                if not 0 <= target < len(code):
                    raise HaltError
                ind += stack[-1]
        elif c == "b":
            if tape[ptr] and stack:
                # jump back X-1: the next command is at ind - X + 1
                target = ind - stack[-1] + 1
                if not 0 <= target < len(code):
                    raise HaltError
                ind -= stack[-1]
        elif c == "o":
            io.print_char(chr(tape[ptr]))
        else:
            raise ValueError(f"unrecognized NoComment command {c!r}")
        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
