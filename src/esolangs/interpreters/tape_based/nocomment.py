"""Interpreter for NoComment.

This interpreter implements a *subset* of NoComment for the text generator:
``c`` clears the current cell, ``i`` increments it, and ``o`` prints it as a
byte; every other character is treated as a comment and ignored.  The wiki
spec defines the full language (``i d c l r n f s b o`` over a tape and
stack, with non-command characters as errors), which the assembly
cross-check implements; this Python interpreter deliberately omits the
tape, the stack, and the jumps, and its comment-ignoring behavior differs
from the wiki's error-on-non-command rule.  With a single cell and no
input, the subset can only print a fixed text, which is exactly what the
generator produces.  ``c``/``i``/``o`` map onto brainfuck's ``[-]``/``+``/
``.``, so the NoComment-to-BF transpiler is a table lookup and is verified
end to end.
"""

import sys

from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    """Run a NoComment program."""
    cell = 0
    for char in code:
        if char == "c":
            cell = 0
        elif char == "i":
            cell = (cell + 1) % 256
        elif char == "o":
            io.print_char(chr(cell))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
