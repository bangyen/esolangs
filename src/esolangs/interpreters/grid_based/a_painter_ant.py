"""Interpreter for A Painter Ant.

A single ant moves over an infinite grid of black or white cells (all black
to start).  The lowercase instructions ``n``/``e``/``s``/``w`` move the ant
one cell in that direction only if the destination cell is black; the
uppercase ``N``/``E``/``S``/``W`` move it only if the destination is white.
``p`` paints the cell under the ant black and ``P`` paints it white.  The
program runs in an implicit loop: after the final instruction, the pointer
returns to the first.

The wiki defines no I/O, so following the repo convention for
interpreter-only languages (Minsky Swap prints its registers), :func:`run`
steps the program, one whole pass at a time, until its state repeats at the
start of a pass -- proof that every pass from there on renders the same
picture -- and then calls :meth:`_Machine.interrupt`, whose next ``step``
prints the bounding box of the cells the ant has visited: a rectangle of
``#`` (white) and ``.`` (black) cells, one row per line, with the ant's own
cell drawn as ``@`` on white or ``o`` on black.  The dump sits in ``step``
behind a guard, as every other interpreter-only language here spells it;
``interrupt`` stands in for the halt this language does not have.
White space is ignored, any other instruction is a malformed program
(:class:`ValueError`, exit 2), and the origin cell counts as visited.

The glyphs are ink, not colour names: every cell starts black, and ``P`` is
what paints one white, so white is the mark the ant has *made* and gets the
dense character.  A painted structure therefore shows up as ink on a blank
field -- the boolean generator's two leaves read as solid diamonds -- rather
than as scattered gaps in a field of ``#``.

Two details of that output are deliberate.

The unit is a *whole pass*, not a step count.  The program is an implicit
infinite loop, so there is no halt to run to, and a raw instruction budget
stops wherever it happens to land: an earlier default of 10,000 instructions
cut the boolean generator's AND2 program at 95.24 passes, mid-pass, with the
ant somewhere in the middle of its walk.  A whole pass is the language's own
natural unit, and every program the boolean generator emits is a
pass-stable fixed point -- its grid and the ant's resting cell are the same
after one pass as after ten, verified by running each generated program to
ten passes and comparing -- so detecting the first repeat renders the same
picture running further would.  A program that never settles into a fixed
routine is stepped for as long as it takes to prove that with certainty
(:func:`run`'s own Brent's-algorithm loop), the way a real interpreter
should; there is no artificial step cap left to cut a divergent program off
early or a stable one off before its repeat is found.

The ant is drawn because otherwise it is invisible.  The raster used to
show painted cells only, which is enough to see *what* the ant drew but not
*where it stopped* -- and for the boolean generator, where it stopped is
the answer (its two leaves are painted rings that look identical, and the
result is which one the ant is resting in).
"""

import sys
from collections.abc import Mapping
from typing import Literal

from esolangs.interpreters.io import IO

# The heading an instruction.
# an unbounded sparse grid.
# horizontal axis here.
# instruction characters that.
_Heading = Literal["n", "e", "s", "w"]

_MOVE: dict[_Heading, tuple[int, int]] = {
    "n": (0, -1),
    "e": (1, 0),
    "s": (0, 1),
    "w": (-1, 0),
}

# An instruction is a heading.
# black cell, uppercase onto a.
# validation string from _MOVE.
# branch can actually look up.
_INSTRUCTIONS = "".join(h + h.upper() for h in _MOVE) + "pP"

# The same headings keyed by.
# can turn a parsed character.
_HEADING: dict[str, _Heading] = {h: h for h in _MOVE}


# : One instant of a run:.
# : cells, the ant's position,.
# : ant has stood on.
# : :data:`_Move` rather than.
# :.
# : The grid has to be in the.
# : to it, so what a move finds.
#: step decided.
# :.
# : ``visited`` is *not* here.
# : ever reads -- only.
# : box -- so the shell records.
# : the transition stays a.
# :.
# : The grid is a read-only.
# : returns a new dict, so the.
# : lookup stays O(1).
# : ``frozenset`` of items.
# : access; on the boolean.
# : thousands of cells over a.
type _Grid = Mapping[tuple[int, int], int]
type _State = tuple[_Grid, int, int, int]

# : What one instruction did:.
# : up, and the single cell it.
# : when it painted nothing.
# : new grid so that recording.
# : a copy of every cell.
# : it to the grid the shell.
type _Move = tuple[int, int, int, tuple[tuple[int, int], int] | None]


def _colour(grid: _Grid, cell: tuple[int, int]) -> int:
    """Return a cell's colour; an unpainted cell is black (``0``)."""
    return grid.get(cell, 0)


def _advance(state: _State, command: str) -> _Move:
    """Return the position after one instruction, plus any paint it made.

    Pure: it reads ``state`` and returns a description of what changed,
    touching nothing.  The language has no I/O at all, so the cursor
    advance is the caller's, since only it knows the program's length.

    The paint comes back as ``(cell, colour)`` rather than as a rewritten
    grid.  Returning a new grid meant copying every painted cell to record
    one -- O(grid) per paint, so a walk that paints ``n`` cells cost
    O(n**2) overall, and the plane runs to thousands of cells.  Naming the
    one cell instead makes a paint O(1) and leaves the shell to apply it.
    The grid is still only *read* here, and still a plain ``Mapping`` so
    that lookup stays O(1) -- the axis the type note above is about.

    A move is conditional on the colour ahead: lowercase goes only onto a
    black cell and uppercase only onto a white one, which is the same test
    written once against ``command.isupper()``.  A refused move is not an
    error -- the ant simply stays, and the cursor still advances.
    """
    grid, x, y, ip = state
    if command == "p":
        return (x, y, ip, ((x, y), 0))
    if command == "P":
        return (x, y, ip, ((x, y), 1))

    # Not a move command at all.
    # the four headings, which is.
    heading = _HEADING.get(command.lower())
    if heading is None:  # pragma: no cover - _INSTRUCTIONS admits no other
        raise ValueError(f"unknown command {command!r}")
    dx, dy = _MOVE[heading]
    if (_colour(grid, (x + dx, y + dy)) == 1) == command.isupper():
        return (x + dx, y + dy, ip, None)
    return (x, y, ip, None)


class _Machine:
    """Per-run A Painter Ant state.

    Holds the grid, the ant's position, and the implicit-loop instruction
    pointer.  ``step()`` executes one instruction (paint or conditional
    move) and advances the instruction pointer cyclically; ``halted`` is
    always ``False`` because the program runs in an implicit loop forever,
    so the VM's generic per-step hang detector
    (:func:`esolangs.vm.run_until_halt_or_cycle`) treats a repeated
    :meth:`snapshot` as the proof of a loop.  :func:`run` below does the
    same proof its own way, snapshotting once per whole pass
    rather than once per step -- see its docstring for why.
    """

    # : Whether the program can.
    # : language, not to whoever is.
    # : ``False``, so ``while not.
    # : caller stepping this one.
    # : detector, or.
    # :.
    # : :func:`run` stops it from.
    # : Brent's cycle detector,.
    self_halts = False

    # : Whether stepping ever.
    # : answer is the rendered grid.
    # : a stepping caller is by.
    # : steps leave ``halted``.
    # : hang and is really a.
    # : does not say so, since.
    #: answer while being stepped.
    # :.
    # : So the flag exists to be.
    # : driving this language by.
    # : :func:`esolangs.run`.
    #: render.
    steppable_to_answer = False

    def __init__(
        self,
        code: str,
        io: IO | None = None,
    ) -> None:
        """Validate ``code`` and reset the machine to the origin.

        ``io`` defaults to a fresh :class:`IO` so a caller that only wants
        to step the grid -- the cycle detector does -- can still build a
        machine without one, as this signature has always allowed.  The
        render is written on the step after :meth:`interrupt`.
        """
        self.io = io if io is not None else IO()
        # Out of ``snapshot``: the dump.
        # detector compares states of a.
        self._interrupted = False
        self._dumped = False
        self.prog = "".join(c for c in code if not c.isspace())
        for c in self.prog:
            if c not in _INSTRUCTIONS:
                raise ValueError(f"unknown instruction {c!r}")
        self.grid: dict[tuple[int, int], int] = {}
        self.visited: set[tuple[int, int]] = {(0, 0)}
        self.x = self.y = 0
        self.ip = 0

    @property
    def halted(self) -> bool:
        """The implicit loop never halts; only a repeated state proves a loop."""
        return False

    # The VM's language-shaped.
    # cell colours.

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [v for _, v in sorted(self.grid.items())]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (frozenset(self.grid.items()), self.x, self.y, self.ip)

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (self.grid, self.x, self.y, self.ip)

    def _restore(self, move: _Move) -> None:
        """Write a transition's result back onto the machine's fields.

        The fields are this class's published shape -- ``render`` walks the
        grid and the tests read the position -- so they stay; the one
        assignment a step makes is here rather than in the rule above.

        The grid is the shell's own dict, so a paint is written into it
        directly.  The transition never held a reference to mutate, having
        only read it and named the cell.
        """
        self.x, self.y, self.ip, paint = move
        if paint is not None:
            cell, colour = paint
            # Written unconditionally.
            # module's counterexample walk.
            # with a ``grid.get(cell, 0) !=.
            # (0.1113s against 0.1095s):.
            # write it saves does.
            # deleting them keeps the two.
            # can tell the difference,.
            # both read through.
            self.grid[cell] = colour
        # Standing on a cell is what.
        # position the transition.
        self.visited.add((self.x, self.y))

    def interrupt(self) -> None:
        """Mark the run finished, so the next :meth:`step` renders.

        **Only sound at a pass boundary** (``ip == 0``).  The render shows
        where the ant *rests*, and the boolean generator reads that resting
        cell, so interrupting mid-pass would draw the ant mid-dance.
        :func:`run` proves its repeat at a boundary and calls this there;
        any other caller owes the same.

        A Painter Ant is an unconditional infinite loop, so ``halted`` is
        always ``False`` and there is no halt to hang the dump on.  This is
        the halt's stand-in, which lets the dump sit in ``step`` behind a
        guard, exactly as the other interpreter-only languages spell it.
        """
        self._interrupted = True

    def step(self) -> None:
        """Execute one instruction, or render once the run is interrupted.

        The cursor advance is here rather than in the transition: it wraps
        modulo the program's length, which is the shell's to know.  So is
        the render, for the usual reason -- this is the shell, so it is
        where an effect belongs -- and ``dumped`` keeps it to exactly one
        render however many times an interrupted machine is stepped.

        The render branch returns *without* advancing.  Stepping first
        would leave the picture one instruction past the boundary
        :meth:`interrupt` was called at, which is the mid-pass render that
        boundary-only detection exists to avoid.
        """
        if self.halted or self._interrupted:
            if not self._dumped:
                self.io.print_str(self.render())
                self._dumped = True
            return
        # ``run`` steps in whole passes.
        # program's pass is zero steps.
        # this keeps a direct caller.
        if not self.prog:  # pragma: no cover - run() never steps an empty program
            return
        x, y, _ip, paint = _advance(self._state, self.prog[self.ip])
        self._restore((x, y, (self.ip + 1) % len(self.prog), paint))

    def render(self) -> str:
        """Render the visited bounding box, marking the ant's cell.

        Four glyphs, one per (cell colour, ant present) pair: ``#`` white
        and ``.`` black, with the ant's own cell as ``@`` on white or ``o``
        on black.  Density tracks the colour in both pairs -- ``#`` and
        ``@`` are the dense ones -- and both ant glyphs are round, so the
        ant reads as one thing at a glance while its colour stays legible.
        """
        min_x = min(vx for vx, _ in self.visited)
        max_x = max(vx for vx, _ in self.visited)
        min_y = min(vy for _, vy in self.visited)
        max_y = max(vy for _, vy in self.visited)
        return "\n".join(
            "".join(self._glyph(xx, yy) for xx in range(min_x, max_x + 1))
            for yy in range(min_y, max_y + 1)
        )

    def _glyph(self, xx: int, yy: int) -> str:
        """Return one cell's character: its colour, and whether the ant is on it."""
        white = self.grid.get((xx, yy), 0) == 1
        if (xx, yy) == (self.x, self.y):
            return "@" if white else "o"
        return "#" if white else "."


def run(code: str, io: IO) -> None:
    """Run an A Painter Ant program until its state repeats at a pass boundary.

    The language is an unconditional infinite loop -- ``halted`` is always
    ``False`` -- so there is no halt to run to and no fixed step count that
    is right for every program.  What every program *does* have is Brent's
    guarantee: a deterministic machine with finitely many reachable states
    must eventually revisit one, and once ``snapshot()`` (position, ip and
    every painted cell) repeats at the start of a pass, every pass from then
    on is identical to the one before it -- the ant is dancing a fixed
    routine on a grid that no longer changes.  That repeat is the render:
    stepping past it would only draw the same picture again.

    Snapshots are taken only at pass boundaries (``ip == 0``), not every
    step, for two reasons.  Perf: a snapshot copies every painted cell, and
    the boolean generator's programs run to thousands of them -- comparing
    on each of a pass's individual steps rather than once per pass turned a
    0.1s test into 134s during development.  Correctness: the boolean
    answer is the cell the ant *rests* on at the end of a whole pass, so a
    cycle proven mid-pass would still leave the render showing the ant
    mid-dance rather than on its resting cell.  Boundary-only detection
    loses no cycles either: the pointer advances by exactly one modulo the
    program's length every step, so any repeated state has a period that is
    a multiple of the program's length, and a state that repeats at all
    therefore repeats at a boundary.

    By the time a repeat is found, the ant has traversed the loop at least
    once since the checkpoint, so ``visited`` -- deliberately excluded from
    ``snapshot()``, since it is append-only bookkeeping no rule reads -- has
    already grown to cover the full eternal picture; the boundary at which
    the repeat is detected renders identically to every boundary after it.
    """
    machine = _Machine(code, io)
    span = len(machine.prog)
    tortoise = machine.snapshot()
    power = 1
    passes = 0
    while True:
        for _ in range(span):
            machine.step()
        passes += 1
        if machine.snapshot() == tortoise:
            break
        if passes == power:
            tortoise = machine.snapshot()
            power *= 2
            passes = 0
    # The loop breaks at a pass.
    # sound; the step after it.
    # step does.
    machine.interrupt()
    machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
