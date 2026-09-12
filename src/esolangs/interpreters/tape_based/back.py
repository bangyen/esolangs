r"""Interpreter for Back."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from esolangs.interpreters.io import IO

# : One instant of a run:.
# : beam's position and.
# : whether the beam has.
# : transition below returns a.
# : the tape is a ``tuple`` for.
# :.
# : ``done`` is state because.
# : fact about the position:.
# : the grid wraps, so no.
# :.
# : ``done`` stays out of.
# : always reported plus the.
# : order it already returned;.
# : snapshot the cycle detector.
# :.
# : The grid is deliberately.
# : so carrying it would put.
# : stores.
type _State = tuple[int, int, int, int, tuple[int, ...], int, bool]


def _advance(state: _State, code: Sequence[str], size: int) -> _State:
    r"""Return the state after executing one grid cell."""
    row, col, a, b, tape, cell, _done = state
    char = code[row][col]
    if char == "\\":
        a, b = b, a
    elif char == "/":
        a, b = -b, -a
    elif char == "<":
        # ``<`` at the origin is.
        if cell:
            cell -= 1
    elif char == ">":
        cell += 1
        # The tape grows a cell to meet.
        if cell == len(tape):
            tape = (*tape, 0)
    elif char == "-":
        tape = (*tape[:cell], tape[cell] ^ 1, *tape[cell + 1 :])
    elif char == "+" and not tape[cell]:
        row, col = row + a, col + b
    elif char == "*":
        # The beam stops where it.
        return (row, col, a, b, tape, cell, True)
    return ((row + a) % len(code), (col + b) % size, a, b, tape, cell, False)


class _Machine:
    r"""Per-run Back state: the beam, the bit tape, and the tape pointer."""

    # : Whether the tape is written.
    # : belongs to the language,.
    # : its loop with one more.
    # : ``halted`` has driven the.
    #: its output.
    dumps_on_the_post_halt_step = True

    def __init__(self, code: list[str], io: IO) -> None:
        r"""Pad ``code`` to a rectangle and start the beam at the top-left."""
        if not code or not any(line.strip() for line in code):
            raise ValueError("Back program cannot be empty")
        self.io = io
        self.size = max(len(line) for line in code)
        self.code = tuple(line.ljust(self.size) for line in code)
        # The beam starts top-left.
        self.state: _State = (0, 0, 0, 1, (0,), 0, False)
        # Out of ``_State``: the dump.
        # keep hashing the fields it.
        self._dumped = False

    # The language's own names.
    # than fields of their own, so.

    @property
    def row(self) -> int:
        return self.state[0]

    @property
    def col(self) -> int:
        return self.state[1]

    @property
    def a(self) -> int:
        return self.state[2]

    @property
    def b(self) -> int:
        return self.state[3]

    @property
    def tape(self) -> tuple[int, ...]:
        return self.state[4]

    @property
    def cell(self) -> int:
        return self.state[5]

    # The growth detector's view.
    # aliased to the name.
    # below already carries the.
    # -- two visits to one grid.
    # the same point in the program.
    # one fresh zero, ``<`` clamps.
    # the code-side wrap ``(row +.
    # the tape, so it does not.
    # the one command that reads.
    # never occur inside a period.

    @property
    def ptr(self) -> int:
        r"""The cell pointer, under the name the growth detector reads."""
        return self.state[5]

    def input_position(self) -> int:
        r"""Report the input cursor for the growth detector."""
        return self.io.position()

    @property
    def halted(self) -> bool:
        r"""Whether the beam has reached a ``*``."""
        return self.state[6]

    @property
    def dumped(self) -> bool:
        r"""Whether the end-of-run tape dump has already been printed."""
        return self._dumped

    # The VM's language-shaped.
    # memory the bit tape.

    # : ``ip`` is a cell of the.
    # : parts are a row and a.
    # : this a caller cannot tell.
    # : stack, which look identical.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...]:
        r"""The current instruction position."""
        row, col, a, b = self.state[:4]
        return (row, col, a, b)

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return list(self.state[4])

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # The six live fields plus the.
        # returned before ``done``.
        # the detector compares states.
        row, col, a, b, tape, cell, _done = self.state
        return (row, col, a, b, tape, cell, self.io.position())

    def step(self) -> None:
        r"""Execute one cell, or dump the tape on the post-halt step."""
        if self.halted:
            if not self.dumped:
                self.io.print_str(" ".join(map(str, self.tape)))
                self._dumped = True
            return
        self.state = _advance(self.state, self.code, self.size)


def run(code: list[str], io: IO) -> None:
    r"""Run a Back program, printing the tape when it halts."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    machine.step()  # the post-halt step prints the.


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
