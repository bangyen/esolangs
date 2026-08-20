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


class _Machine:
    """Per-run 2dFish state: position, direction, accumulator, string mode.

    ``step()`` executes the cell under the pointer and advances it;
    ``halted`` is true once the pointer hits ``@`` or leaves the grid.  A
    pointer that runs off the grid halts with the documented
    :class:`HaltError` in :func:`run` (it is *not* a normal halt).  The
    VM and the state-cycle hang detector expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code`` and set the initial direction from the top-left."""
        self.io = io
        self.grid = _read_lines(code)
        self.acc = 0
        self.string = ""
        self.mode = False
        self._done = False
        self._off_grid = False

        # the top-left cell only sets the initial direction (an empty first
        # row reads as the NUL char, which is not a direction)
        first = "\0" if not self.grid[0] else self.grid[0][0]
        self.x, self.y, self.d = _direct(first, 0, 0, None)
        if self.d is None:
            raise ValueError("program does not set an initial direction")

    @property
    def halted(self) -> bool:
        """Whether the pointer hit ``@`` or left the grid."""
        return self._done

    @property
    def off_grid(self) -> bool:
        """Whether the pointer ran off the grid (the documented exit-3 halt)."""
        return self._off_grid

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.x,
            self.y,
            self.d,
            self.acc,
            self.string,
            self.mode,
            self.io.position(),
        )

    def step(self) -> None:
        """Execute one command, advancing the pointer."""
        if self._done:
            return
        if (
            self.y < 0
            or self.x < 0
            or self.y >= len(self.grid)
            or self.x >= len(self.grid[self.y])
        ):
            self._done = True
            self._off_grid = True
            return

        c = self.grid[self.y][self.x]
        if c == "@":
            self._done = True
            return

        if c == "i":
            self.mode = False
            self.acc += 1
        elif c == "d":
            self.mode = False
            self.acc -= 1
        elif c == "s":
            self.mode = False
            self.acc *= self.acc
        elif c == "o":
            self.io.print_num(self.acc)
        elif c == "a":
            if self.mode:
                if not self.string:
                    raise HaltError("a on an empty string")
                self.io.print_char(self.string[-1])
                self.string = self.string[:-1]
            else:
                self.io.print_char(chr(self.acc % 256))
        elif c == "$":
            self.string = self.io.input_str("Input: ")
        elif c == "%":
            self.mode = False
            self.acc = self.io.input_num("Input: ")
        elif c == "(":
            self.string = ""
            self.mode = True
            if ")" not in self.grid[self.y][self.x :]:
                raise ValueError("unterminated ( string capture")
            temp = self.x
            self.x += 1
            while self.grid[self.y][self.x] != ")":
                self.string += self.grid[self.y][self.x]
                self.x += 1
            if self.d != "/":
                self.x = temp
        elif c == "*":
            self.io.print_str(self.string)
            self.string = ""

        self.x, self.y, self.d = _direct(c, self.x, self.y, self.d)


def run(code: str, io: IO) -> None:
    """Run a 2dFish program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    if machine.off_grid:  # mirrors the documented exit-3 halt
        raise HaltError("pointer moved off the grid")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
