"""Interpreter for A Painter Ant.

An ant on an infinite black grid: ``n``/``e``/``s``/``w`` move onto a
black cell, ``N``/``E``/``S``/``W`` onto a white one, ``p``/``P`` paint;
the program loops.  Whitespace is ignored.  A whole pass is the unit: a
10,000-instruction budget once cut AND2 mid-pass at 95.24 passes.  Every
generated program is a pass-stable fixed point (verified to ten passes); a
divergent one is stepped until Brent's proves it.

Input/output:
    No input.  :func:`run` steps whole passes until the state repeats at a
    pass start, then interrupts the machine so the next ``step`` prints the
    visited box: ``#`` white, ``.`` black, the ant ``@``/``o`` (where it
    rests is the boolean answer).

Errors:
    ProgramError: any character but ``nsew``, ``NSEW``, ``pP`` and
    whitespace (exit 2).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

# ``(dx, dy)``; named so a heading stays distinct from its character.
_Heading = Literal["n", "e", "s", "w"]

_MOVE: dict[_Heading, tuple[int, int]] = {
    "n": (0, -1),
    "e": (1, 0),
    "s": (0, 1),
    "w": (-1, 0),
}

# Derived from _MOVE so validation matches what the move branch looks up.
_INSTRUCTIONS = "".join(h + h.upper() for h in _MOVE) + "pP"

# Headings keyed by spelling, so the move branch needs no assert.
_HEADING: dict[str, _Heading] = {h: h for h in _MOVE}


#: The shell's grid is borrowed read-only; freezing it per step turned a
#: 0.1s test into 134s on thousand-cell grids. Paint leaves as an effect.
type _Grid = Mapping[tuple[int, int], int]
type _State = tuple[int, int, int]

#: ``(x, y, ip, paint)``, paint = ``(cell, colour)`` or None.  One write
#: per step instead of a grid copy; :meth:`_Machine._restore` applies it.
type _Move = tuple[int, int, int, tuple[tuple[int, int], int] | None]


def _advance(state: _State, grid: _Grid, program: str) -> _Move:
    """Return the position after one instruction, plus any paint it made.

    Pure; the paint comes back as
    ``(cell, colour)`` rather than a rewritten grid (O(grid) per paint made a
    walk O(n**2) over thousands of cells).  A refused move is not an error.
    """
    x, y, ip = state
    command = program[ip]
    ip = (ip + 1) % len(program)
    if command == "p":
        return (x, y, ip, ((x, y), 0))
    if command == "P":
        return (x, y, ip, ((x, y), 1))

    # Only a move if the lowercased character is a heading.
    heading = _HEADING.get(command.lower())
    if heading is None:  # pragma: no cover - _INSTRUCTIONS admits no other
        raise syntax_error(
            f"unknown command {command!r}",
            "use only n/e/s/w or N/E/S/W to move, and p/P to paint",
        )
    dx, dy = _MOVE[heading]
    if (grid.get((x + dx, y + dy), 0) == 1) == command.isupper():
        return (x + dx, y + dy, ip, None)
    return (x, y, ip, None)


class _Machine:
    """Per-run A Painter Ant state.

    ``halted`` is always ``False``, so :func:`esolangs.vm.run_until_halt_or_cycle`
    uses a repeated :meth:`snapshot`; :func:`run` does the same once per pass.
    """

    #: ``halted`` is always False; ``while not vm.halted`` never returns.
    #: :func:`run` stops it with a pass-boundary Brent's detector, then renders.
    self_halts = False

    #: The answer is the render after the walk is proven periodic; use
    #: :func:`esolangs.run` (some languages carry ``self_halts = False`` too).
    steppable_to_answer = False

    def __init__(
        self,
        code: str,
        io: IO | None = None,
    ) -> None:
        """Validate ``code`` and reset the machine to the origin.

        ``io`` defaults to a fresh :class:`IO` so the cycle detector can build a
        machine without one.
        """
        self.io = io if io is not None else IO()
        # Not in ``snapshot``: the dump is bookkeeping, not machine state.
        self._interrupted = False
        self._dumped = False
        self.prog = "".join(c for c in code if not c.isspace())
        for c in self.prog:
            if c not in _INSTRUCTIONS:
                raise syntax_error(
                    f"unknown instruction {c!r}",
                    "use only n/e/s/w or N/E/S/W to move, and p/P to paint",
                )
        self.grid: dict[tuple[int, int], int] = {}
        self._view = MappingProxyType(self.grid)
        # ``snapshot``'s grid, rebuilt only after a paint changes a cell: past
        # pass 1 almost none do, so a per-step snapshot stops costing O(grid).
        self._frozen: frozenset[tuple[tuple[int, int], int]] | None = None
        self.visited: set[tuple[int, int]] = {(0, 0)}
        self.x = self.y = 0
        self.ip = 0

    @property
    def halted(self) -> bool:
        """The implicit loop never halts; only a repeated state proves a loop."""
        return False

    # VM view: ip is the instruction cursor, memory the cell colours.

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [v for _, v in sorted(self.grid.items())]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        if self._frozen is None:
            self._frozen = frozenset(self.grid.items())
        return (self._frozen, self.x, self.y, self.ip)

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (self.x, self.y, self.ip)

    def _restore(self, move: _Move) -> None:
        """Write a transition's result back onto the machine's fields.

        The grid is the shell's own dict; the transition only named the cell.
        """
        self.x, self.y, self.ip, paint = move
        if paint is not None:
            cell, colour = paint
            # Guarded: 73.7% of paints are redundant, and only a real change
            # may drop ``snapshot``'s cached grid.  Black is stored, not
            # deleted; ``_glyph`` and ``_advance`` read via ``grid.get(cell, 0)``.
            if self.grid.get(cell) != colour:
                self.grid[cell] = colour
                self._frozen = None
        # Standing on a cell marks it visited.
        self.visited.add((self.x, self.y))

    def interrupt(self) -> None:
        """Mark the run finished, so the next :meth:`step` renders.

        Only sound at a pass boundary (``ip == 0``): mid-pass would draw the ant
        mid-dance.  The halt's stand-in, so the dump sits in ``step`` behind a guard.
        """
        self._interrupted = True

    def step(self) -> None:
        """Execute one instruction, or render once the run is interrupted.

        The transition wraps the cursor modulo the program length; ``dumped`` keeps the
        render to one.  The render branch does not advance, or the picture
        would be one instruction past the boundary.
        """
        if self._interrupted:
            if not self._dumped:
                self.io.print_str(self.render())
                self._dumped = True
            return
        # ``run`` never steps an empty program; this guards direct callers.
        if not self.prog:  # pragma: no cover - run() never steps an empty program
            return
        self._restore(_advance(self._state, self._view, self.prog))

    def render(self) -> str:
        """Render the visited bounding box, marking the ant's cell.

        ``#``/``.`` for white/black, ``@``/``o`` for the ant on each; density
        tracks colour and both ant glyphs are round.
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

    Once ``snapshot()`` repeats at a pass start every later pass is
    identical.  Boundaries only: a snapshot copies every painted cell
    (per-step comparison turned 0.1s into 134s), the answer is the resting
    cell, and no cycle is lost since the pointer advances by one modulo the
    length.  ``visited`` (excluded from the snapshot) has covered the full
    picture by then.
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
    # Breaks at a pass boundary, where ``interrupt`` is sound; the step
    # after renders, like a post-halt step.
    machine.interrupt()
    machine.step()


if __name__ == "__main__":
    script_main(run)
