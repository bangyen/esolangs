r"""Interpreter for Keys.

The first two lines are compared; the program prints "Accept." when they are
equal and contain none of the characters ``- _ / \\``, otherwise "Reject."

A program with fewer than two lines is malformed; this interpreter raises
:class:`ValueError` rather than indexing past the end.
"""

import re
import sys

from esolangs.interpreters.io import IO


def run(code: list[str], io: IO) -> None:
    """Accept or reject the two lines in ``code``."""
    if len(code) < 2:
        raise ValueError("Keys program must contain at least two lines")
    x = code[0].strip()
    y = code[1].strip()
    r = re.compile(r"(-_|_-|\\-|/" r"_|[^\\/\-_])")

    if x == y and not r.search(x):
        io.print_line("Accept.")
    else:
        io.print_line("Reject.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
