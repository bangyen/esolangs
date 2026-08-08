"""Interpreter for NoComment.

NoComment is a strict subset of brainfuck: ``c`` clears the current cell,
``i`` increments it, and ``o`` prints it as a byte; every other character
is a comment.  With a single cell and no input, a program can only print a
fixed text, which is exactly what the generator produces.  ``c``/``i``/``o``
map onto brainfuck's ``[-]``/``+``/``.``, so the NoComment-to-BF transpiler
is a table lookup and is verified end to end.
"""

import sys


def run(code: str) -> None:
    cell = 0
    for char in code:
        if char == "c":
            cell = 0
        elif char == "i":
            cell = (cell + 1) % 256
        elif char == "o":
            print(chr(cell), end="")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read())
