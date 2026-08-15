r"""Interpreter for Back.

A beam bounces across a grid at right angles: \\ and / reflect its direction,
< and > move the tape pointer, - flips the current bit, + steps the beam
forward when the current bit is 0, and * halts, printing the tape.
"""

import sys

from esolangs.interpreters.io import IO


def run(code: list[str], io: IO) -> None:
    """Run a Back program and print the tape when it halts."""
    if not code or not any(line.strip() for line in code):
        raise ValueError("Back program cannot be empty")
    size = max(len(lne) for lne in code)
    code = [c.ljust(size) for c in code]

    x = y = 0
    a, b = 0, 1
    tape: list[int] = [0]
    cell = 0

    while True:
        if (c := code[x][y]) == "\\":
            a, b = b, a
        elif c == "/":
            a, b = -b, -a
        elif c == "<":
            if cell:
                cell -= 1
        elif c == ">":
            cell += 1
            if cell == len(tape):
                tape.append(0)
        elif c == "-":
            tape[cell] ^= 1
        elif c == "+" and not tape[cell]:
            x, y = x + a, y + b
        elif c == "*":
            break

        x = (x + a) % len(code)
        y = (y + b) % size

    io.print_line(" ".join(map(str, tape)))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
