"""Interpreter for Clockwise.

A pointer walks clockwise around a square ring, turning at R cells (or at ?
when the accumulator is nonzero, or ! when it is zero).  ; outputs the
accumulator parity, . reads an input bit, S zeroes the accumulator, and seven
parity bits are grouped into one printed byte.
"""

import sys

from esolangs.interpreters.io import IO

COL = [1, 0, -1, 0]
ROW = [0, 1, 0, -1]


def move(
    x: int,
    y: int,
    r: int,
    code: list[str],
    acc: int,
) -> tuple[int, int, int, str, int]:
    """Step the pointer one cell, returning position, direction, and the cell."""
    o = code[y][x]
    c = (o == "R") or (o == "?" and acc) or (o == "!" and not acc)

    r = (r + c) % 4
    x += COL[r]
    y += ROW[r]
    b = x or y or not r

    return x, y, r, o, b


def run(code: list[str], io: IO) -> None:
    """Run a Clockwise program, reading input bits when the ring reads ``.``."""
    size = max(len(lne) for lne in code)
    code = [c.ljust(size) for c in code]
    x = y = r = 0
    cont = 1

    inp: list[str] = []
    out: list[str] = []
    acc = 0

    if "." in "".join(code):
        for k in io.input_str():
            val = f"{ord(k):07b}"
            inp += list(val.zfill(7))

    while cont:
        x, y, r, ins, cont = move(x, y, r, code, acc)
        if ins in "R?!":
            continue
        if ins == "+":
            acc += 1
        elif ins == "-":
            acc -= 1
        elif ins == ".":
            n = int(inp[0])
            acc = (acc | 1) - 1 + n
            inp = [*inp[1:], inp[0]]
        elif ins == ";":
            out.append(str(acc % 2))
        elif ins == "S":
            acc = 0

        if len(out) == 7:
            char_val: int = int("".join(out), 2)
            io.print_char(chr(char_val))
            out = []


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
