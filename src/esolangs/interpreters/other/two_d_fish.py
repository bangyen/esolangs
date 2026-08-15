r"""Interpreter for 2dFish.

A pointer travels a grid of rows; the top-left cell must set its direction
(``/`` right, ``\\`` left, ``v`` down, ``^`` up) and every cell it lands on
is executed as a command: ``i``/``d``/``s`` increment/decrement/square the
accumulator, ``o`` prints it in decimal, ``a`` prints it as a byte (or, in
string mode, the last captured character, which it removes), ``$`` reads an
input line into the string variable, ``%`` reads an integer into the accumulator, ``(``
captures the rest of its row up to the first ``)`` as the string variable
and (heading right) skips past it, ``*`` prints and clears the string
variable, and ``@`` halts.  The direction cell on the current cell also
redirects the pointer, so a direction both steers and executes as a no-op.
Execution is a straight line in the current direction: the language has no
flow control.

The semantics (including the quirk below) are ported exactly from the Rust
cross-check at ``extra/rust/2dfish.rs``:

- the grid is *ragged*: the pointer is off the grid when it leaves any row,
  not a padded rectangle, and stepping off the grid halts with
  :class:`HaltError` (exit 3);
- ``(`` scans its row forward to the first ``)``; the captured text is the
  characters strictly between them, and a ``(`` with no ``)`` on its row is
  a malformed program (:class:`ValueError`, exit 2); after capturing, a
  right-moving pointer lands just past the ``)``, while any other direction
  resumes moving from the ``(``;
- the cross-check's ``while (!file.eof()) getline(...)`` loop pushes the last
  line a second time when the program text ends with a newline, so a
  program file that ends in ``\\n`` has one extra phantom copy of its last
  row; the interpreter reproduces this (it is observable: a pointer that
  descends past the last real row can execute the phantom row before
  stepping off the grid).

Documented divergences (the cross-check leaves these undefined or broken):

- exhausted input raises :class:`EOFError` (repo-wide convention) instead of
  the cross-checks exiting with status 3;
- ``a`` in string mode with an empty string (which the Rust cross-check's
  ``str[0]`` makes undefined) raises :class:`HaltError`;
- ``a`` outside string mode writes the accumulator's low byte
  (``chr(acc % 256)``), matching the cross-check's two's-complement
  truncation rather than raising on out-of-range values.
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_DIRS = "/\\v^"


def _read_lines(code: str) -> list[str]:
    """Split ``code`` into rows the way the cross-check reads its file.

    The cross-check's ``while (!file.eof()) getline(...)`` loop pushes the
    last line a second time when the text ends with a newline (the final
    ``getline`` fails at EOF and leaves the string unchanged); without a
    trailing newline the final ``getline`` hits EOF and the loop ends.  An
    empty program is one row containing the empty string.
    """
    rows = code.split("\n")
    if code.endswith("\n"):
        rows = rows[:-1]
        rows.append(rows[-1])
    return rows


def _get(grid: list[str], x: int, y: int) -> str:
    """Return the cell at ``(x, y)``, or halt if the pointer left the grid."""
    if y < 0 or x < 0 or y >= len(grid) or x >= len(grid[y]):
        raise HaltError("pointer moved off the grid")
    return grid[y][x]


def _direct(c: str, x: int, y: int, d: str | None) -> tuple[int, int, str | None]:
    """If ``c`` sets a direction, adopt it, then take one step in it."""
    if c in _DIRS:
        d = c
    if d == "/":
        x += 1
    elif d == "\\":
        x -= 1
    elif d == "v":
        y += 1
    elif d == "^":
        y -= 1
    return x, y, d


def run(code: str, io: IO) -> None:
    """Run a 2dFish program."""
    grid = _read_lines(code)

    x = y = 0
    acc = 0
    string = ""
    mode = False
    d: str | None = None

    # the top-left cell only sets the initial direction (an empty first row
    # reads as the NUL char, which is not a direction)
    first = "\0" if not grid[0] else grid[0][0]
    x, y, d = _direct(first, x, y, d)
    if d is None:
        raise ValueError("program does not set an initial direction")

    c = _get(grid, x, y)

    while c != "@":
        if c == "i":
            mode = False
            acc += 1
        elif c == "d":
            mode = False
            acc -= 1
        elif c == "s":
            mode = False
            acc *= acc
        elif c == "o":
            io.print_num(acc)
        elif c == "a":
            if mode:
                if not string:
                    raise HaltError("a on an empty string")
                io.print_char(string[-1])
                string = string[:-1]
            else:
                io.print_char(chr(acc % 256))
        elif c == "$":
            string = io.input_str("Input: ")
        elif c == "%":
            mode = False
            acc = io.input_num("Input: ")
        elif c == "(":
            string = ""
            mode = True
            if ")" not in grid[y][x:]:
                raise ValueError("unterminated ( string capture")
            temp = x
            x += 1
            while grid[y][x] != ")":
                string += grid[y][x]
                x += 1
            if d != "/":
                x = temp
        elif c == "*":
            io.print_str(string)
            string = ""

        x, y, d = _direct(c, x, y, d)
        c = _get(grid, x, y)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
