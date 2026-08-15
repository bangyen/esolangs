"""Interpreter for Circlefuck.

The tape is the program itself: cells wrap, + and - adjust the current cell,
, reads input, . outputs, [ and ] jump to matching brackets reading the cell,
@ halts, { and } insert and remove cells, and the pointer moves around the
circular tape.

A program with no instructions is malformed and is rejected with
:class:`ValueError`, as is one with unmatched ``[``/``]`` brackets; deleting
the last cell (``}``) is an invalid operation and halts the program with
:class:`~esolangs.exceptions.HaltError`.
"""

import re
import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


def parse(code: str) -> list[int]:
    """Decode Circlefuck's escape sequences and keep printable commands only."""
    reg = r"\\(?:\d\d\d|" r"[\dA-F](?:$|[^\d]))"
    exp = r"((^|[^\\]) |\\( )|(\\)o)"

    for s in re.findall(reg, code):
        if len(s) == 4:
            val = oct(int(s[1:]))
            new = val[2:].zfill(3)
        else:
            new = f"x0{s[1:]}"
        code = code.replace(s, f"\\{new}")

    code = re.sub(exp, r"\2\3\4", code)
    code = "".join(c for c in code if 31 < ord(c) < 127)
    code = bytes(code, "utf-8").decode("unicode_escape")

    return [ord(c) for c in code]


def find(code: list[int], ind: int, ptr: int) -> int:
    """Return the matching bracket for ``ind``.

    Raises :class:`ValueError` if the brackets are unbalanced: the wiki
    defines ``[``/``]`` only for matched pairs, so an unmatched bracket is a
    malformed program.
    """
    char = chr(code[ind])
    if char == "[":
        if code[ptr]:
            return ind
        mode = 1
    else:
        if not code[ptr]:
            return ind
        mode = -1

    match = mode
    start = ind
    num = len(code)

    while match:
        ind = (ind + mode) % num
        sym = chr(code[ind])
        if ind == start:
            raise ValueError("unmatched bracket")
        if sym == "[":
            match += 1
        elif sym == "]":
            match -= 1
    return ind


def run(code: str, io: IO) -> None:
    """Run a Circlefuck program."""
    cells: list[int] = parse(code)
    if not cells:
        raise ValueError("Circlefuck program cannot be empty")
    ind = ptr = 0

    while True:
        if (char := chr(cells[ind])) == ">":
            ptr = (ptr + 1) % len(cells)
        elif char == "<":
            ptr = (ptr - 1) % len(cells)
        elif char == "+":
            cells[ptr] = (cells[ptr] + 1) % 256
        elif char == "-":
            cells[ptr] = (cells[ptr] - 1) % 256
        elif char == ",":
            cells[ptr] = io.input_char()
        elif char in "[]":
            ind = find(cells, ind, ptr)
        elif char == ".":
            val = chr(cells[ptr])
            io.print_char(val)
        elif char == "@":
            return
        elif char == "#":
            ind += 1
        elif char == "{":
            cells.insert(ptr, 0)
            ind += 1
        elif char == "}":
            if len(cells) == 1:
                raise HaltError
            cells.pop(ptr)

        ind = (ind + 1) % len(cells)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
