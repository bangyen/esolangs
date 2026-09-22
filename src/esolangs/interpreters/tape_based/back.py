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
``step()`` executes one cell, setting ``halted`` when the beam reaches a
``*`` and printing the tape on the step after that -- the post-halt dump
the other interpreter-only languages here share.

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

from collections.abc import Sequence

from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

#: ``(row, col, a, b, tape, cell, done)``: an immutable value, rebound per
#: step.  ``done`` is state because the beam sits *on* the ``*`` and the
#: grid wraps, so no position means "stopped"; it stays out of ``snapshot``
#: (six fields plus input cursor, in the order always returned).  The grid
#: is a parameter, not a field, so the cycle detector stores no constants.
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
        # Clamped at the origin.
        if cell:
            cell -= 1
    elif char == ">":
        cell += 1
        # Grows to meet the pointer.
        if cell == len(tape):
            tape = (*tape, 0)
    elif char == "-":
        tape = (*tape[:cell], tape[cell] ^ 1, *tape[cell + 1 :])
    elif char == "+" and not tape[cell]:
        row, col = row + a, col + b
    elif char == "*":
        # Stops in place; the dump is the shell's.
        return (row, col, a, b, tape, cell, True)
    return ((row + a) % len(code), (col + b) % size, a, b, tape, cell, False)


class _Machine:
    """Per-run Back state: the beam, the bit tape, and the tape pointer.

    ``step()`` executes one cell, setting ``halted`` when the beam reaches
    a ``*`` and printing the tape on the step after that.  The VM and the
    state-cycle hang detector expose this object.
    """

    #: The tape is dumped on the step *after* the halt; a caller who stops
    #: at ``halted`` holds no output.
    dumps_on_the_post_halt_step = True

    def __init__(self, code: list[str], io: IO) -> None:
        """Pad ``code`` to a rectangle and start the beam at the top-left."""
        if not code or not any(line.strip() for line in code):
            raise ValueError("Back program cannot be empty")
        self.io = io
        self.size = max(len(line) for line in code)
        self.code = tuple(line.ljust(self.size) for line in code)
        # Top-left heading right; (a, b) is (d_row, d_col).
        self.state: _State = (0, 0, 0, 1, (0,), 0, False)
        # Not in ``_State``: the dump is the shell's.
        self._dumped = False

    # Views on the state.

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

    # ``_TapeMachine`` view: ``cell`` aliased to the pointer name; ``ip``
    # carries direction (same square, different heading is a different
    # point).  Back qualifies: ``>`` appends one zero, ``<`` clamps at 0,
    # the code wrap moves the beam not the tape, and ``*`` (the only
    # whole-tape read) halts, so it is never inside a compared period.

    @property
    def ptr(self) -> int:
        """The cell pointer, under the name the growth detector reads."""
        return self.state[5]

    def input_position(self) -> int:
        """Report the input cursor for the growth detector."""
        return self.io.position()

    @property
    def halted(self) -> bool:
        """Whether the beam has reached a ``*``."""
        return self.state[6]

    @property
    def dumped(self) -> bool:
        """Whether the end-of-run tape dump has already been printed."""
        return self._dumped

    # VM view: ip is (row, col, direction), memory the bit tape.

    #: ``ip`` is (row, col, heading) in the program rectangle; without this
    #: a caller cannot tell it from a call depth or frame stack.
    ip_shape = "grid"

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
        # Six live fields plus input cursor; ``done`` stays out.
        row, col, a, b, tape, cell, _done = self.state
        return (row, col, a, b, tape, cell, self.io.position())

    def step(self) -> None:
        """Execute one cell, or dump the tape on the post-halt step.

        The dump is here rather than in the transition: this is the shell,
        so it is where an effect belongs.  ``*`` is Back's halt command and
        nothing else sets ``halted``, so the halt is the guard -- the
        character that caused it does not have to be read back off the
        grid.

        It fires on the step *after* the halt, as Minsky Swap, Bitdeque,
        RAM0, ArrowQueue and LaserFuck all do: a caller who drives the
        machine itself then sees the same output from all six, rather than
        holding Back's tape and none of the others'.  ``dumped`` keeps it
        to one dump however many times a halted machine is stepped.
        """
        if self.halted:
            if not self.dumped:
                self.io.print_str(" ".join(map(str, self.tape)))
                self._dumped = True
            return
        self.state = _advance(self.state, self.code, self.size)


def run(code: list[str], io: IO) -> None:
    """Run a Back program, printing the tape when it halts."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    machine.step()  # the post-halt step prints the tape


if __name__ == "__main__":
    script_main(run, shape="keep")
