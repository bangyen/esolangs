r"""Interpreter for Back.

A beam bounces across a grid at right angles: \\ and / reflect its direction,
< and > move the tape pointer, - flips the current bit, + steps the beam
forward when the current bit is 0, and * halts, printing the tape.

The wiki says only "Halt the program" of ``*`` and defines no output at all,
so the dump follows the repo convention for interpreter-only languages
(Minsky Swap prints its registers): the cells space-separated on one line,
with no trailing newline.  Both the choice to print and the separator are
this interpreter's.  (LaserFuck uses line breaks between values instead, but
that is not a divergence from this convention -- its spec asks for them by
name.)

The interpreter runs on a :class:`_Machine` (the beam's position and
direction, the bit tape, and the tape pointer), so it is step-capable:
``step()`` executes one cell, printing the tape and setting ``halted`` when
the beam reaches a ``*``.

A program with no ``*`` bounces the beam forever.  The beam itself lives in
a finite grid, so a loop that never moves the tape pointer right revisits a
snapshot and ``esolangs.vm.run_until_halt_or_cycle`` proves it.  A loop that
crosses ``>`` does not: the pointer advances and the tape grows a cell to
meet it, so the snapshot is new every step and no repeat exists to find.
That is the unbounded-growth case the detector documents itself as unable to
catch, and only the wall-clock timeout stops it.  (The empty program is
rejected outright, so the fuzz suite's empty-program invariant is unaffected.)

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and the grid to the next state, and never
mutates what it is given.  It takes no ``io`` argument at all, so it is
total and side-effect free by construction rather than by inspection.  The
tape is a tuple, so a state is a value that can be stored, compared, and
hashed as it stands.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what Back *does* stays in the
pure layer.  The one effect the language has -- ``*`` printing the tape --
is done by ``step`` before it calls the pure transition.

Malformed programs raise :class:`ValueError`.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from esolangs.interpreters.io import IO

#: One instant of a run: ``(row, col, a, b, tape, cell, done)`` -- the
#: beam's position and direction vector, the bit tape, the tape pointer, and
#: whether the beam has reached a ``*``.  A value, not a record: every
#: transition below returns a new one rather than editing one in place, and
#: the tape is a ``tuple`` for the same reason.
#:
#: ``done`` is state because halting here is a decision a cell makes, not a
#: fact about the position: the beam sits *on* the ``*`` when it stops, and
#: the grid wraps, so no position means "stopped".
#:
#: ``done`` stays out of ``snapshot``, which reports the six fields it
#: always reported plus the input cursor.  The field order there is the
#: order it already returned; reordering would silently reorder every
#: snapshot the cycle detector has hashed.
#:
#: The grid is deliberately not in here.  It does not change during a run,
#: so carrying it would put constant data in every value the cycle detector
#: stores.  It is a parameter to the transition instead.
type _State = tuple[int, int, int, int, tuple[int, ...], int, bool]


def _advance(state: _State, code: Sequence[str], size: int) -> _State:
    """Return the state after executing one grid cell.

    Pure: it reads ``state`` and returns a new one.  It takes no ``io``
    argument, so ``*``'s tape dump is necessarily the caller's business --
    this function only records, through ``done``, that the beam stopped.

    ``+`` is the one cell that moves the beam twice: it steps forward when
    the current bit is zero, and then takes the shared move below like
    every other cell.  That is what makes it a skip rather than a jump.

    The shared move wraps in both axes, so the beam never leaves the grid
    -- which is why a program with no ``*`` bounces forever rather than
    running off the edge.
    """
    row, col, a, b, tape, cell, _done = state
    char = code[row][col]
    if char == "\\":
        a, b = b, a
    elif char == "/":
        a, b = -b, -a
    elif char == "<":
        # ``<`` at the origin is clamped rather than an error.
        if cell:
            cell -= 1
    elif char == ">":
        cell += 1
        # The tape grows a cell to meet the pointer.
        if cell == len(tape):
            tape = (*tape, 0)
    elif char == "-":
        tape = (*tape[:cell], tape[cell] ^ 1, *tape[cell + 1 :])
    elif char == "+" and not tape[cell]:
        row, col = row + a, col + b
    elif char == "*":
        # The beam stops where it stands; the dump is the shell's.
        return (row, col, a, b, tape, cell, True)
    return ((row + a) % len(code), (col + b) % size, a, b, tape, cell, False)


class _Machine:
    """Per-run Back state: the beam, the bit tape, and the tape pointer.

    ``step()`` executes one cell, printing the tape and setting ``halted``
    when the beam reaches a ``*``.  The VM and the state-cycle hang detector
    expose this object.
    """

    __slots__ = ("code", "io", "size", "state")

    def __init__(self, code: list[str], io: IO) -> None:
        """Pad ``code`` to a rectangle and start the beam at the top-left."""
        if not code or not any(line.strip() for line in code):
            raise ValueError("Back program cannot be empty")
        self.io = io
        self.size = max(len(line) for line in code)
        self.code = tuple(line.ljust(self.size) for line in code)
        # The beam starts top-left heading right: (a, b) is (d_row, d_col).
        self.state: _State = (0, 0, 0, 1, (0,), 0, False)

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

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

    @property
    def halted(self) -> bool:
        """Whether the beam has reached a ``*``."""
        return self.state[6]

    # The VM's language-shaped view: 2D beam; ip is the beam's (row, col, direction),
    # memory the bit tape.

    @property
    def ip(self) -> tuple[int, ...]:
        """The current instruction position."""
        row, col, a, b = self.state[:4]
        return (row, col, a, b)

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.state[4])

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The six live fields plus the input cursor, in the order this
        # returned before ``done`` joined the state.  ``done`` stays out:
        # the detector compares states of a running machine.
        row, col, a, b, tape, cell, _done = self.state
        return (row, col, a, b, tape, cell, self.io.position())

    def step(self) -> None:
        """Execute one cell, moving the beam.

        The tape dump is here rather than in the transition: this is the
        shell, so it is where an effect belongs.  It fires on the step that
        reaches the ``*``, before the transition records the stop.
        """
        if self.state[6]:
            return
        row, col, _a, _b, tape, _cell, _done = self.state
        if self.code[row][col] == "*":
            self.io.print_str(" ".join(map(str, tape)))
        self.state = _advance(self.state, self.code, self.size)


def run(code: list[str], io: IO) -> None:
    """Run a Back program, printing the tape when it halts."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
