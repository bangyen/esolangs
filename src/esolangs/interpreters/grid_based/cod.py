r"""Interpreter for COD.

COD programs are a 2D grid of "waves" (``~``, walls) and "water" (passable
cells).  A cod is a moving instruction pointer with an unbounded signed
integer value, starting at 0.  Commands, executed when a cod passes over
them:

- ``+`` duplicates the cod; ``-`` removes it.
- ``)``/``(`` increment/decrement the cod's value.
- ``<`` removes the cod if its value is zero.
- ``_`` reacts only to upward motion: a cod moving up is sent back down iff
  its value is nonzero; otherwise it is a no-op.
- ``---`` (three dashes with nothing between, touching the left or right
  edge) prints the cod's value and removes it; the same three characters
  anywhere else are three separate ``-`` removals.
- ``...`` (three periods with nothing between, touching the top or bottom
  edge) reads a number from stdin into the cod's value; elsewhere it is
  ignored (water).

The wiki's own truth-machine example uses a single ``.`` for input rather
than ``...``, which is not itself a documented command; this interpreter
follows the prose spec (a genuine three-in-a-row, edge-touching run) rather
than that example, so the sample program does not read input as written.

A cod continues straight when its forward cell is open.  When forward is
blocked, it considers every other open cell except the one it just left: one
open cell is a forced turn, none is a dead end (it reverses), and two or more
is a random junction.  ``+`` is different: it counts the open cells *besides*
the one the cod entered from (so on a straight corridor, "2 branches" means
forward and back, i.e. no real fork) and splits deterministically among the
forward-facing options — this matches the wiki's "if there are two branches,
one will continue and one will go back; if there are three, they will each
go different forward branches" (the fourth "otherwise random" case cannot
occur on a rectangular grid, where at most three cells besides the entry
exist).  The program terminates once no cod remains.
"""

import secrets
import sys
from typing import Protocol

from esolangs.interpreters.io import IO


class _Chooser(Protocol):
    """Picks one of several open directions, overriding ``secrets``."""

    def choice(self, options: list[str]) -> str: ...


_DIRS = {"N": (-1, 0), "S": (1, 0), "E": (0, 1), "W": (0, -1)}
_OPP = {"N": "S", "S": "N", "E": "W", "W": "E"}
_COMMANDS = set("+-)(<_")


def _edge_dash_cells(grid: list[str]) -> set[tuple[int, int]]:
    """Cells belonging to a ``---`` run that touches the left or right edge."""
    width = len(grid[0]) if grid else 0
    cells: set[tuple[int, int]] = set()
    for r, row in enumerate(grid):
        c = 0
        while c < len(row):
            if row[c] == "-":
                start = c
                while c < len(row) and row[c] == "-":
                    c += 1
                if c - start == 3 and (start == 0 or c == width):
                    cells.update((r, cc) for cc in range(start, c))
            else:
                c += 1
    return cells


def _edge_dot_cells(grid: list[str]) -> set[tuple[int, int]]:
    """Cells belonging to a ``...`` run that touches the top or bottom edge."""
    height = len(grid)
    width = len(grid[0]) if grid else 0
    cells: set[tuple[int, int]] = set()
    for c in range(width):
        r = 0
        while r < height:
            if grid[r][c] == ".":
                start = r
                while r < height and grid[r][c] == ".":
                    r += 1
                if r - start == 3 and (start == 0 or r == height):
                    cells.update((rr, c) for rr in range(start, r))
            else:
                r += 1
    return cells


class _Cod:
    """A single instruction pointer: position, heading, and value."""

    __slots__ = ("c", "d", "r", "value")

    def __init__(self, r: int, c: int, d: str, value: int = 0) -> None:
        self.r, self.c, self.d, self.value = r, c, d, value


class _Machine:
    """Per-run COD state: the grid and every live cod.

    ``step()`` advances every live cod by one cell and executes the command
    it lands on; ``halted`` is true once no cod remains.  Randomness (a
    genuine multi-way junction, or a ``+`` split beyond three branches,
    which cannot occur on a rectangular grid) is drawn from ``secrets`` by
    default; ``rng`` overrides it for reproducible stepping (the VM and
    tests).
    """

    def __init__(self, code: str, io: IO, rng: _Chooser | None = None) -> None:
        self.io = io
        self._rng = rng
        rows = code.split("\n")
        while rows and rows[-1] == "":
            rows.pop()
        width = max((len(row) for row in rows), default=0)
        self.grid = [row.ljust(width, "~") for row in rows]
        _passable = _COMMANDS | set("->.")
        for row in self.grid:
            for ch in row:
                if ch != "~" and ch != " " and ch not in _passable:
                    raise ValueError(f"unknown instruction {ch!r}")

        self._edge_dashes = _edge_dash_cells(self.grid)
        self._edge_dots = _edge_dot_cells(self.grid)

        self.cods: list[_Cod] = []
        started = False
        for r, row in enumerate(self.grid):
            for c, ch in enumerate(row):
                if ch == ">":
                    if started:
                        raise ValueError("multiple cod start markers")
                    started = True
                    opens = self._open_dirs(r, c)
                    if not opens:
                        raise ValueError("cod start is fully enclosed")
                    d = opens[0] if len(opens) == 1 else self._choose(opens)
                    self.cods.append(_Cod(r, c, d, 0))
        if not started:
            raise ValueError("no cod start marker '>'")

    # -- geometry -----------------------------------------------------

    def _cell(self, r: int, c: int) -> str:
        if r < 0 or r >= len(self.grid) or c < 0 or c >= len(self.grid[0]):
            return "~"
        return self.grid[r][c]

    def _is_open(self, r: int, c: int) -> bool:
        return self._cell(r, c) != "~"

    def _open_dirs(self, r: int, c: int, exclude: str | None = None) -> list[str]:
        return [
            d
            for d, (dr, dc) in _DIRS.items()
            if d != exclude and self._is_open(r + dr, c + dc)
        ]

    def _choose(self, options: list[str]) -> str:
        if self._rng is not None:
            return self._rng.choice(options)
        return options[secrets.randbelow(len(options))]

    # -- state ----------------------------------------------------------

    @property
    def halted(self) -> bool:
        return not self.cods

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            tuple(sorted((cod.r, cod.c, cod.d, cod.value) for cod in self.cods)),
            self.io.position(),
        )

    # -- stepping ---------------------------------------------------------

    def step(self) -> None:
        """Advance every live cod by one cell, executing what it lands on."""
        if not self.cods:
            return
        next_cods: list[_Cod] = []
        for cod in self.cods:
            next_cods.extend(self._advance(cod))
        self.cods = next_cods

    def _advance(self, cod: _Cod) -> list[_Cod]:
        dr, dc = _DIRS[cod.d]
        if self._is_open(cod.r + dr, cod.c + dc):
            move_dir = cod.d
        else:
            alts = self._open_dirs(cod.r, cod.c, exclude=_OPP[cod.d])
            if not alts:
                move_dir = _OPP[cod.d]
            elif len(alts) == 1:
                move_dir = alts[0]
            else:
                move_dir = self._choose(alts)
        mdr, mdc = _DIRS[move_dir]
        r, c = cod.r + mdr, cod.c + mdc
        cod.r, cod.c, cod.d = r, c, move_dir

        if (r, c) in self._edge_dashes:
            self.io.print_line(str(cod.value))
            return []

        ch = self._cell(r, c)
        if (r, c) in self._edge_dots:
            cod.value = self.io.input_num()
            return [cod]
        if ch == ")":
            cod.value += 1
        elif ch == "(":
            cod.value -= 1
        elif ch == "-":
            return []
        elif ch == "<":
            if cod.value == 0:
                return []
        elif ch == "_":
            if cod.d == "N" and cod.value != 0:
                cod.d = "S"
        elif ch == "+":
            came_from = _OPP[cod.d]
            branches = self._open_dirs(r, c, exclude=came_from)
            if not branches:
                return [_Cod(r, c, came_from, cod.value)]
            return [_Cod(r, c, bd, cod.value) for bd in branches]
        return [cod]


def run(code: str, io: IO, limit: int = 1_000_000, rng: _Chooser | None = None) -> None:
    """Run a COD program until no cod remains, or ``limit`` steps elapse."""
    machine = _Machine(code, io, rng=rng)
    for _ in range(limit):
        if machine.halted:
            break
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
