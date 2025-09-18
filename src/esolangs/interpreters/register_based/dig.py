"""
Dig interpreter implementation.

Dig is a 2D esoteric programming language with a 3rd dimension for "digging".
The language features a mole (pointer) that moves on a 2D grid and can dig underground
to access work commands. Movement commands work overground, while work commands
only function underground after digging.

Based on the specification at https://esolangs.org/wiki/Dig
"""

import sys
from typing import Callable


def run(code: list[str], func: Callable[[], bool] = lambda: False) -> None:
    """
    Execute a Dig program.

    The interpreter manages a mole (pointer) that moves on a 2D grid. The mole can
    move overground using movement commands and dig underground to access work commands.
    The mole has a memory value that starts at 0 and can be modified by various commands.

    Args:
        code: List of strings representing the 2D program grid
        func: Optional function that can terminate execution when called during $ command

    Movement Commands (overground):
        ^ - Point mole up
        > - Point mole right
        ' - Point mole down
        < - Point mole left
        # - Rotate based on adjacent value (0=left, 1=right, other=straight)
        $ - Dig underground for N moves (N = adjacent value)
        @ - Halt execution

    Work Commands (underground only):
        % - Set memory to space (0) or newline (1) based on adjacent value
        = - Read character input into memory
        ~ - Read integer input into memory
        : - Output memory value and reset to 0
        + - Add adjacent value to memory
        - - Subtract adjacent value from memory
        * - Multiply memory by adjacent value
        / - Divide memory by adjacent value (integer division)
        ; - Store current memory value at current position
        alphanumeric/.,!? - Set memory to ASCII value of character
    """
    size = max(len(lne) for lne in code)
    code = [c.ljust(size) for c in code]

    direct = [(-1, 0), (0, 1), (1, 0), (0, -1)]
    line = mole = num = x = y = 0
    move = 1

    def value() -> int:
        """
        Get the first digit value from adjacent cells.

        Searches in order: up, right, down, left for the first digit character
        and returns its integer value. Used by commands that need numeric values.

        Returns:
            Integer value of the first digit found in adjacent cells
        """
        lst = []
        for i, j in direct:
            if 0 <= x + i < len(code) and 0 <= y + j < size:
                val = code[x + i][y + j]
                if val.isdigit():
                    lst.append(int(val))
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
                temp = input("\n" * line + "Input: ")
                line = False

                if char == "=":
                    mole = ord(temp[0])
                else:
                    mole = int(temp[0])
            elif char == ":":
                if mole < 10:
                    print(mole, end="")
                else:
                    print(chr(mole), end="")

                line = True
                mole = 0
            elif char == "+":
                mole += value()
            elif char == "-":
                mole -= value()
            elif char == "*":
                mole += value()
            elif char == "/":
                mole //= value()
            elif char == ";":
                code[x] = code[x][:y] + str(mole) + code[x][y + 1 :]
            elif char.isdigit():
                mole = int(char)
            elif char.isalpha() or char in ".,!?":
                mole = ord(char)
            num -= 1
        else:
            if char in "^>'<":
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


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
