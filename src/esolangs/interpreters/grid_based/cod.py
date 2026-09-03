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
  edge) prints the cod's value -- with no separator, per the wiki's bare
  "output the cod's value" -- and removes it; the same three characters
  anywhere else are three separate ``-`` removals.
- ``...`` (three periods with nothing between, touching the top or bottom
  edge) reads a number from stdin into the cod's value; elsewhere it is
  ignored (water).

The wiki's own truth-machine example does contain a valid ``...``: column 2,
rows 0-2, touching the top edge, which :func:`_edge_dot_cells` accepts.  (The
dots in the neighbouring columns do not break it -- the spec's "without any
waves or other characters in between" constrains the run along its own
column.)

Each of the three dot cells is its own read, so the read count depends on how
a cod meets the run: crossing horizontally enters one cell and reads once,
while turning *into* the column reads three times for what the spec calls a
single command.  A generator wanting one read per input must cross
horizontally.

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

Malformed programs -- an unknown instruction, no ``>`` start marker, more
than one of them, or a start that is fully enclosed -- raise
:class:`ValueError`.  A read also raises :class:`ValueError` when the line
it is given is not an integer, since a read parses its line as a number.

At EOF a read raises :class:`EOFError` out of :meth:`IO.input_num`, which
propagates: the cod has already swum onto the reading dot by then, so the
move is committed before the read and the exception unwinds from a
consistent state.  No :class:`HaltError` is raised.  A COD program need not
terminate at all -- ``run`` takes a ``limit`` of steps and simply returns
once it elapses, rather than raising, because a swimming cod that never
leaves the grid is normal behavior and not an error.
"""

import sys
from collections.abc import Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Literal

from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import Randomness, draw

# The four directions a cod swims in.  Naming them keeps a direction apart
# from the grid characters that are also plain strings, so the _DIRS and
# _OPP lookups are checked rather than trusted.
_Direction = Literal["N", "S", "E", "W"]


_DIRS: dict[_Direction, tuple[int, int]] = {
    "N": (-1, 0),
    "S": (1, 0),
    "E": (0, 1),
    "W": (0, -1),
}
_OPP: dict[_Direction, _Direction] = {"N": "S", "S": "N", "E": "W", "W": "E"}
_COMMANDS = set("+-)(<_")


def _edge_dash_cells(grid: Sequence[str]) -> set[tuple[int, int]]:
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


def _edge_dot_cells(grid: Sequence[str]) -> set[tuple[int, int]]:
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


@dataclass(frozen=True)
class _Cod:
    """A single instruction pointer: position, heading, and value.

    Frozen, because the cods *are* the state: a step maps each one forward
    into zero, one, or several successors rather than editing it in place.
    """

    r: int
    c: int
    d: _Direction
    value: int = 0


def _cell(grid: Sequence[str], r: int, c: int) -> str:
    """Return the character at ``(r, c)``; off the grid reads as water."""
    if r < 0 or r >= len(grid) or c < 0 or c >= len(grid[0]):
        return "~"
    return grid[r][c]


def _open(grid: Sequence[str], r: int, c: int) -> bool:
    """Whether a cod can swim into ``(r, c)``."""
    return _cell(grid, r, c) != "~"


def _open_dirs(
    grid: Sequence[str], r: int, c: int, exclude: _Direction | None = None
) -> list[_Direction]:
    """Return the headings out of ``(r, c)`` that are not water."""
    return [
        d
        for d, (dr, dc) in _DIRS.items()
        if d != exclude and _open(grid, r + dr, c + dc)
    ]


#: What one cod's step wants done: print its value, or take a number from
#: the input port.  A step advances *every* live cod, so the effects are a
#: list -- Eval's shape, for the same reason.
@dataclass(frozen=True)
class _Print:
    """Write a cod's value."""

    value: int


@dataclass(frozen=True)
class _Read:
    """Take a number; the cod that asked is at ``index`` in the new list."""

    index: int


type _Effect = _Print | _Read


def _step_cod(
    cod: _Cod,
    grid: Sequence[str],
    dashes: AbstractSet[tuple[int, int]],
    dots: AbstractSet[tuple[int, int]],
    turn: int | None,
) -> tuple[list[_Cod], list[_Effect]]:
    """Return the cods that follow ``cod``, and what it wants done.

    Pure: it reads its arguments and returns a description.  A cod that
    reaches a dash on the border prints and dies, one that reaches a dot
    reads, one that meets a bare dash or a failed zero-test dies, and one
    that meets a junction becomes several.

    ``turn`` is the caller's draw, used only when more than one way out is
    open; everything else about the move is decided here.
    """
    dr, dc = _DIRS[cod.d]
    if _open(grid, cod.r + dr, cod.c + dc):
        move_dir = cod.d
    else:
        alts = _open_dirs(grid, cod.r, cod.c, exclude=_OPP[cod.d])
        if not alts:
            move_dir = _OPP[cod.d]
        elif len(alts) == 1:
            move_dir = alts[0]
        else:
            move_dir = alts[turn if turn is not None else 0]
    mdr, mdc = _DIRS[move_dir]
    r, c = cod.r + mdr, cod.c + mdc
    moved = _Cod(r, c, move_dir, cod.value)

    if (r, c) in dashes:
        return ([], [_Print(moved.value)])

    ch = _cell(grid, r, c)
    if (r, c) in dots:
        return ([moved], [_Read(0)])
    if ch == ")":
        return ([_Cod(r, c, move_dir, moved.value + 1)], [])
    if ch == "(":
        return ([_Cod(r, c, move_dir, moved.value - 1)], [])
    if ch == "-":
        return ([], [])
    if ch == "<":
        return ([], []) if moved.value == 0 else ([moved], [])
    if ch == "_":
        if move_dir == "N" and moved.value != 0:
            return ([_Cod(r, c, "S", moved.value)], [])
        return ([moved], [])
    if ch == "+":
        came_from = _OPP[move_dir]
        branches = _open_dirs(grid, r, c, exclude=came_from)
        if not branches:
            return ([_Cod(r, c, came_from, moved.value)], [])
        return ([_Cod(r, c, bd, moved.value) for bd in branches], [])
    return ([moved], [])


class _Machine:
    """Per-run COD state: the grid and every live cod.

    ``step()`` advances every live cod by one cell and executes the command
    it lands on; ``halted`` is true once no cod remains.  Randomness (a
    genuine multi-way junction, or a ``+`` split beyond three branches,
    which cannot occur on a rectangular grid) is drawn for real by
    default; ``rng`` overrides it for reproducible stepping (the VM and
    tests), and is the shared hook every random language here uses.
    """

    #: The seed a reproducible run starts from.  It belongs to the
    #: language, not to whoever is stepping it: 1 sends the wiki's own
    #: junction example East, the way its walkthrough goes.
    reproducible_seed = 1

    def __init__(self, code: str, io: IO, rng: Randomness | None = None) -> None:
        self.io = io
        self._rng = rng
        rows = code.split("\n")
        while rows and rows[-1] == "":
            rows.pop()
        width = max((len(row) for row in rows), default=0)
        self.grid = tuple(row.ljust(width, "~") for row in rows)
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

    def _open_dirs(
        self, r: int, c: int, exclude: _Direction | None = None
    ) -> list[_Direction]:
        return _open_dirs(self.grid, r, c, exclude)

    def _choose(self, options: list[_Direction]) -> _Direction:
        return options[draw(self._rng, len(options))]

    # -- state ----------------------------------------------------------

    @property
    def halted(self) -> bool:
        return not self.cods

    # The VM's language-shaped view.

    @property
    def ip(self) -> tuple[int, ...]:
        """Every live cod's ``(row, col, heading, value)``, flattened.

        A COD program can have several cods running at once, so there is no
        single cursor: they are sorted for a stable order and concatenated,
        with the heading coded as its index into ``_DIRS`` above.
        """
        order = list(_DIRS)
        cods = sorted(
            (cod.r, cod.c, order.index(cod.d), cod.value) for cod in self.cods
        )
        return tuple(v for cod in cods for v in cod)

    @property
    def memory(self) -> list[int]:
        """Each live cod's carried value."""
        return [cod.value for cod in self.cods]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            tuple(sorted((cod.r, cod.c, cod.d, cod.value) for cod in self.cods)),
            self.io.position(),
        )

    # -- stepping ---------------------------------------------------------

    def step(self) -> None:
        """Advance every live cod by one cell, executing what it lands on.

        The ports live here rather than in the transition: this is the
        shell.  A cod that reaches a dash on the border prints, and one
        that reaches a dot reads -- both in cod order, so a step with
        several live cods writes what they write in the order they are
        carried.  A junction's draw is made here too, and only when more
        than one way out is open.
        """
        if not self.cods:
            return
        next_cods: list[_Cod] = []
        remaining = list(self.cods)
        for index, cod in enumerate(remaining):
            turn = None
            if not _open(self.grid, cod.r + _DIRS[cod.d][0], cod.c + _DIRS[cod.d][1]):
                alts = _open_dirs(self.grid, cod.r, cod.c, exclude=_OPP[cod.d])
                if len(alts) > 1:
                    turn = draw(self._rng, len(alts))
            grown, effects = _step_cod(
                cod, self.grid, self._edge_dashes, self._edge_dots, turn
            )
            for effect in effects:
                if isinstance(effect, _Print):
                    self.io.print_str(str(effect.value))
                else:
                    # The cod has already swum onto the dot by the time it
                    # reads, and the original left it there when the port
                    # raised at EOF -- so commit the move first.
                    self.cods = [*next_cods, *grown, *remaining[index + 1 :]]
                    read = self.io.input_num()
                    grown = [
                        _Cod(k.r, k.c, k.d, read) if i == effect.index else k
                        for i, k in enumerate(grown)
                    ]
            next_cods.extend(grown)
        self.cods = next_cods


def run(
    code: str, io: IO, limit: int = 1_000_000, rng: Randomness | None = None
) -> None:
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
