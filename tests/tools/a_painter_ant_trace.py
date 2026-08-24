"""Step-by-step tracer and cycle-stability checker for A Painter Ant programs.

The interpreter prints only the bounding box of the cells the ant has
visited (a raster that carries no coordinates), which is enough to confirm
that a program is a cycle-stable fixed point, and to read the generator's
answer off the ant's own cell, but not to see why a later cycle diverges.
The boolean generator reads its answer from the same semantic grid model
this module exposes:

- :func:`run` steps the ant command by command and records every blocked
  move, fired move, and paint, so a diverging cycle can be pinned to the
  exact instruction.
- :func:`box` renders the interpreter's bounding box from that model, and
  :func:`cycle_stable` compares the box across whole numbers of cycles.
- :func:`first_divergence` runs cycles 1 and 2 and reports the first
  instruction where the ant's position, effect, or paint disagrees with
  cycle 1 -- the feedback loop the n == 3 cycle-2 construction needs.

The command set matches :mod:`esolangs.interpreters.grid_based.a_painter_ant`:
lowercase moves fire only onto black cells, uppercase only onto white,
``p`` paints the current cell black, ``P`` paints it white, and whitespace
is ignored (a space in the source is a no-op that still occupies a
position).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

_MOVE = {"n": (0, -1), "e": (1, 0), "s": (0, 1), "w": (-1, 0)}
_PAINTS = "pP"

Action = Literal["blocked", "moved", "paint_black", "paint_white"]


@dataclass(frozen=True)
class Step:
    """One executed instruction: its position, effect, and move target."""

    index: int
    command: str
    position: tuple[int, int]
    action: Action
    target: tuple[int, int] | None


@dataclass
class Run:
    """The semantic outcome of running a program for whole cycles."""

    grid: dict[tuple[int, int], int]
    visited: set[tuple[int, int]]
    position: tuple[int, int]
    steps: list[Step]
    landings: list[tuple[int, int]]

    def landing_colour(self) -> int:
        """Colour of the cell the ant rests on after the run (1 white, 0 black)."""
        return self.grid.get(self.position, 0)


@dataclass(frozen=True)
class Divergence:
    """The first instruction where the re-run breaks cycle stability."""

    index: int
    command: str
    position: tuple[int, int]
    step1: Step
    step2: Step


def run(program: str, cycles: int = 1) -> Run:
    """Step ``program`` for ``cycles`` whole cycles on the semantic grid.

    Whitespace is ignored (matching the interpreter), and each instruction
    records where the ant was, what it did, and its move target.  The
    ``landings`` list captures the ant's position after each whole cycle.
    """
    prog = [c for c in program if not c.isspace()]
    for c in prog:
        if c.lower() not in _MOVE and c not in _PAINTS:
            raise ValueError(f"unknown instruction {c!r}")

    grid: dict[tuple[int, int], int] = {}
    visited: set[tuple[int, int]] = {(0, 0)}
    x = y = 0
    steps: list[Step] = []
    landings: list[tuple[int, int]] = []
    length = len(prog)
    for i, command in enumerate(prog * cycles):
        if command == "p":
            grid[(x, y)] = 0
            steps.append(Step(i % length, command, (x, y), "paint_black", None))
        elif command == "P":
            grid[(x, y)] = 1
            steps.append(Step(i % length, command, (x, y), "paint_white", None))
        else:
            dx, dy = _MOVE[command.lower()]
            target = (x + dx, y + dy)
            if (grid.get(target, 0) == 1) == command.isupper():
                x, y = target
                visited.add((x, y))
                steps.append(Step(i % length, command, (x, y), "moved", target))
            else:
                steps.append(Step(i % length, command, (x, y), "blocked", target))
        if (i + 1) % length == 0:
            landings.append((x, y))
    return Run(grid, visited, (x, y), steps, landings)


def box(program: str, cycles: int = 1) -> str:
    """Render the interpreter's bounding-box raster from the semantic grid.

    Mirrors the interpreter's four glyphs: ``#`` white, ``.`` black, and the
    ant's own cell as ``@`` on white or ``o`` on black.
    """
    outcome = run(program, cycles)
    min_x = min(vx for vx, _ in outcome.visited)
    max_x = max(vx for vx, _ in outcome.visited)
    min_y = min(vy for _, vy in outcome.visited)
    max_y = max(vy for _, vy in outcome.visited)

    def glyph(xx: int, yy: int) -> str:
        white = outcome.grid.get((xx, yy), 0) == 1
        if (xx, yy) == outcome.position:
            return "@" if white else "o"
        return "#" if white else "."

    return "\n".join(
        "".join(glyph(xx, yy) for xx in range(min_x, max_x + 1))
        for yy in range(min_y, max_y + 1)
    )


def landing_after(program: str, cycles: int = 6) -> int:
    """Landing-cell colour after ``cycles`` cycles (the generator's answer)."""
    return run(program, cycles).landing_colour()


def cycle_stable(program: str, cycles: int = 10) -> bool:
    """Compare the interpreter's box for 1 and ``cycles`` whole cycles."""
    return box(program, 1) == box(program, cycles)


def first_divergence(program: str) -> Divergence | None:
    """Report the first instruction that breaks cycle stability.

    A program is a cycle-stable fixed point when the interpreter's box is
    identical for every whole number of cycles and the landing colour never
    changes.  Because the cycle-2 run is a different walk on purpose (the
    dance), per-instruction equality with cycle 1 is *not* the criterion.
    This checks, in order of severity:

    1. a cycle-2 move that leaves the cycle-1 bounding box (the box grows),
    2. a cycle-2 paint that changes a cell's colour (the box content
       changes),
    3. a cycle-2 landing colour different from cycle 1's (the answer
       changes),
    4. a cycle-3 step that differs from cycle 2 (the dance is not yet a
       fixed point, so later cycles could still drift).

    A program that passes all four checks returns ``None``.
    """
    first = run(program, 1)
    second = run(program, 2)
    third = run(program, 3)
    min_x = min(vx for vx, _ in first.visited)
    max_x = max(vx for vx, _ in first.visited)
    min_y = min(vy for _, vy in first.visited)
    max_y = max(vy for _, vy in first.visited)
    length = len([c for c in program if not c.isspace()])

    for i, step in enumerate(second.steps[length:]):
        if step.action == "moved" and not (
            min_x <= step.position[0] <= max_x and min_y <= step.position[1] <= max_y
        ):
            return Divergence(i, step.command, step.position, first.steps[i], step)
        if step.action in ("paint_black", "paint_white"):
            colour = 1 if step.action == "paint_white" else 0
            if first.grid.get(step.position) != colour:
                return Divergence(i, step.command, step.position, first.steps[i], step)

    if second.landing_colour() != first.landing_colour():
        return Divergence(
            length - 1,
            second.steps[-1].command,
            second.position,
            first.steps[-1],
            second.steps[-1],
        )

    for i, (step2, step3) in enumerate(
        zip(second.steps[length:], third.steps[2 * length :], strict=True)
    ):
        if step2 != step3:
            return Divergence(i, step2.command, step2.position, step2, step3)
    return None
