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
picture -- and then prints the bounding box of the cells the ant has
visited: a rectangle of ``#`` (white) and ``.`` (black) cells, one row per
line, with the ant's own cell drawn as ``@`` on white or ``o`` on black.
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

# The heading an instruction moves along, as (dx, dy).  The ant's plane is
# an unbounded sparse grid rather than rows of text, so x really is the
# horizontal axis here.  Naming the four keeps a heading distinct from the
# instruction characters that spell it in either case.
_Heading = Literal["n", "e", "s", "w"]

_MOVE: dict[_Heading, tuple[int, int]] = {
    "n": (0, -1),
    "e": (1, 0),
    "s": (0, 1),
    "w": (-1, 0),
}

# An instruction is a heading in either case -- lowercase moves onto a
# black cell, uppercase onto a white one -- or a paint.  Deriving the
# validation string from _MOVE keeps it in step with the headings the move
# branch can actually look up.
_INSTRUCTIONS = "".join(h + h.upper() for h in _MOVE) + "pP"

# The same headings keyed by their own spelling, so the move branch
# can turn a parsed character into a _Heading without asserting it.
_HEADING: dict[str, _Heading] = {h: h for h in _MOVE}


#: One instant of a run: ``(grid, x, y, ip, visited)`` -- the painted
#: cells, the ant's position, the instruction cursor, and every cell the
#: ant has stood on.  A value :func:`_advance` maps forward rather than
#: editing in place.
#:
#: The grid has to be in the state, unlike WII2D's: ``p`` and ``P`` write
#: to it, so what a move finds ahead of the ant is something an earlier
#: step decided.
#:
#: ``visited`` is *not* here.  It is append-only bookkeeping that no rule
#: ever reads -- only :meth:`_Machine.render` does, to size the bounding
#: box -- so the shell records it from the position each step returns, and
#: the transition stays a function of what actually decides a move.
#:
#: The grid is a read-only ``Mapping`` rather than a frozen copy: a paint
#: returns a new dict, so the value handed in is left as it was, while a
#: lookup stays O(1).  That is not a nicety.  Freezing it into a
#: ``frozenset`` of items reads well and costs a full rebuild on every
#: access; on the boolean generator's programs, whose grids run to
#: thousands of cells over a cycle, it turned a 0.1s test into a 134s one.
type _Grid = Mapping[tuple[int, int], int]
type _State = tuple[_Grid, int, int, int]


def _colour(grid: _Grid, cell: tuple[int, int]) -> int:
    """Return a cell's colour; an unpainted cell is black (``0``)."""
    return grid.get(cell, 0)


def _paint(grid: _Grid, cell: tuple[int, int], colour: int) -> _Grid:
    """Return ``grid`` with ``cell`` set to ``colour``, replacing any entry.

    A copy, so the grid handed in is left as it was; this is the only
    place a step grows the plane, so it is the only copy a step makes.
    """
    return {**grid, cell: colour}


def _advance(state: _State, command: str) -> _State:
    """Return the state after executing one instruction.

    Pure: it reads ``state`` and returns a new one.  The language has no
    I/O at all, so unlike the other steps in this series there is no effect
    for a shell to keep -- the whole instruction lives here, and the cursor
    advance is the caller's, since only it knows the program's length.

    A move is conditional on the colour ahead: lowercase goes only onto a
    black cell and uppercase only onto a white one, which is the same test
    written once against ``command.isupper()``.  A refused move is not an
    error -- the ant simply stays, and the cursor still advances.
    """
    grid, x, y, ip = state
    if command == "p":
        return (_paint(grid, (x, y), 0), x, y, ip)
    if command == "P":
        return (_paint(grid, (x, y), 1), x, y, ip)

    # Not a move command at all unless the lowercased character is one of
    # the four headings, which is what the lookup requires.
    heading = _HEADING.get(command.lower())
    if heading is None:  # pragma: no cover - _INSTRUCTIONS admits no other
        raise ValueError(f"unknown command {command!r}")
    dx, dy = _MOVE[heading]
    if (_colour(grid, (x + dx, y + dy)) == 1) == command.isupper():
        return (grid, x + dx, y + dy, ip)
    return state


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

    #: Whether the program can reach a halt of its own.  It belongs to the
    #: language, not to whoever is stepping it: ``halted`` here is always
    #: ``False``, so ``while not vm.halted: vm.step()`` never returns.  A
    #: caller stepping this one has to bound the run itself -- with a hang
    #: detector, or :func:`esolangs.run`'s ``timeout``.
    #:
    #: :func:`run` stops it from outside, by its own means: a pass-boundary
    #: Brent's cycle detector, then the render.
    self_halts = False

    def __init__(
        self,
        code: str,
        io: IO | None = None,  # noqa: ARG002 - see ``run``
    ) -> None:
        """Validate ``code`` and reset the machine to the origin.

        ``io`` is accepted and ignored: the language writes only the final
        render, which :func:`run` prints, and taking the parameter anyway
        lets every caller build a machine the same way.
        """
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

    # The VM's language-shaped view: 2D grid; ip is the instruction cursor, memory the
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

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields.

        The fields are this class's published shape -- ``render`` walks the
        grid and the tests read the position -- so they stay; the one
        assignment a step makes is here rather than in the rule above.
        """
        grid, self.x, self.y, self.ip = state
        # dict() only when the transition actually replaced it; a step that
        # did not paint hands back the very object it was given.
        self.grid = grid if isinstance(grid, dict) else dict(grid)
        # Standing on a cell is what marks it visited, so recording the
        # position the transition returned covers every move.
        self.visited.add((self.x, self.y))

    def step(self) -> None:
        """Execute one instruction, advancing the pointer cyclically.

        The cursor advance is here rather than in the transition: it wraps
        modulo the program's length, which is the shell's to know.
        """
        # ``run`` steps in whole passes of ``len(prog)``, so an empty
        # program's pass is zero steps and it is never stepped at all;
        # this keeps a direct caller from indexing it.
        if not self.prog:  # pragma: no cover - run() never steps an empty program
            return
        grid, x, y, _ip = _advance(self._state, self.prog[self.ip])
        self._restore((grid, x, y, (self.ip + 1) % len(self.prog)))

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
    machine = _Machine(code)
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
    io.print_str(machine.render())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
