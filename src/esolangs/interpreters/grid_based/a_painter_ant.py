r"""Interpreter for A Painter Ant."""

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
    r"""Return a cell's colour; an unpainted cell is black (``0``)."""
    return grid.get(cell, 0)


def _advance(state: _State, command: str) -> _Move:
    r"""Return the position after one instruction, plus any paint it made."""
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
    r"""Per-run A Painter Ant state."""

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
        r"""Validate ``code`` and reset the machine to the origin."""
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
        r"""The implicit loop never halts; only a repeated state proves a loop."""
        return False

    # The VM's language-shaped.
    # cell colours.

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return [v for _, v in sorted(self.grid.items())]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (frozenset(self.grid.items()), self.x, self.y, self.ip)

    @property
    def _state(self) -> _State:
        r"""The machine's fields as the value the transition works on."""
        return (self.grid, self.x, self.y, self.ip)

    def _restore(self, move: _Move) -> None:
        r"""Write a transition's result back onto the machine's fields."""
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
        r"""Mark the run finished, so the next :meth:`step` renders."""
        self._interrupted = True

    def step(self) -> None:
        r"""Execute one instruction, or render once the run is interrupted."""
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
        r"""Render the visited bounding box, marking the ant's cell."""
        min_x = min(vx for vx, _ in self.visited)
        max_x = max(vx for vx, _ in self.visited)
        min_y = min(vy for _, vy in self.visited)
        max_y = max(vy for _, vy in self.visited)
        return "\n".join(
            "".join(self._glyph(xx, yy) for xx in range(min_x, max_x + 1))
            for yy in range(min_y, max_y + 1)
        )

    def _glyph(self, xx: int, yy: int) -> str:
        r"""Return one cell's character: its colour, and whether the ant is on."""
        white = self.grid.get((xx, yy), 0) == 1
        if (xx, yy) == (self.x, self.y):
            return "@" if white else "o"
        return "#" if white else "."


def run(code: str, io: IO) -> None:
    r"""Run an A Painter Ant program until its state repeats at a pass."""
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
