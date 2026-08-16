"""Dig interpreter implementation.

2D esoteric language with a mole that moves on a grid and can dig underground.
Movement commands work overground, work commands function underground.

The wiki only lists ``@`` as a halt; this interpreter also stops the program
(without error) when the mole walks off the grid.  A work command that needs a
digit from an adjacent cell but finds none, or divides by an adjacent zero, is
an invalid runtime operation and halts the program with
:class:`~esolangs.exceptions.HaltError`; an empty program is malformed and
rejected with :class:`ValueError`.

Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import sys
from collections.abc import Callable

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


def run(
    code: list[str],
    io: IO,
    func: Callable[[], bool] = lambda: False,
) -> None:
    """Execute a Dig program with mole movement and underground work commands."""
    if not code or not any(line.strip() for line in code):
        raise ValueError("Dig program cannot be empty")
    size = max(len(lne) for lne in code)
    code = [c.ljust(size) for c in code]

    direct = [(-1, 0), (0, 1), (1, 0), (0, -1)]
    mole = num = x = y = 0
    move = 1

    def value() -> int:
        """Get the first digit value from adjacent cells."""
        lst = []
        for i, j in direct:
            if 0 <= x + i < len(code) and 0 <= y + j < size:
                val = code[x + i][y + j]
                if val.isdigit():
                    lst.append(int(val))
        if not lst:
            raise HaltError
        return lst[0]

    while True:
        char = code[x][y]
        if num:
            if char == "%":
                if (n := value()) == 1:
                    mole = 10
                elif n == 0:
                    mole = 32
            elif char in "=~":
                temp = io.input_str()

                if not temp:
                    mole = 0
                elif char == "=":
                    mole = ord(temp[0])
                else:
                    mole = int(temp[0])
            elif char == ":":
                if mole < 10:
                    io.print_num(mole)
                else:
                    io.print_char(chr(mole))

                mole = 0
            elif char == "+":
                mole += value()
            elif char == "-":
                mole -= value()
            elif char == "*":
                mole *= value()
            elif char == "/":
                n = value()
                if n == 0:
                    raise HaltError
                mole //= n
            elif char == ";":
                code[x] = code[x][:y] + str(mole) + code[x][y + 1 :]
            elif char.isdigit():
                mole = int(char)
            elif char.isalpha() or char in ".,!?":
                mole = ord(char)
            num -= 1
        elif char in "^>'<":
            move = "^>'<".find(char)
        elif char == "#":
            if (n := value()) == 1:
                move += 1
            elif n == 0:
                move -= 1
            move %= 4
        elif char == "$":
            if func():
                break
            num = value()
        elif char == "@":
            break

        x += direct[move][0]
        y += direct[move][1]

        # Bounds checking to prevent IndexError
        if x < 0 or x >= len(code) or y < 0 or y >= size:
            break


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
