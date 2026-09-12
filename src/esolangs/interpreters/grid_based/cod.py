r"""Interpreter for COD."""

import sys
from collections.abc import Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Literal, cast

from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import Randomness, draw

# The four directions a cod.
# from the grid characters that.
# _OPP lookups are checked.
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
    r"""Cells belonging to a ``---`` run that touches the left or right."""
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
    r"""Cells belonging to a ``...`` run that touches the top or bottom."""
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
    r"""A single instruction pointer: position, heading, and value."""

    r: int
    c: int
    d: _Direction
    value: int = 0


def _cell(grid: Sequence[str], r: int, c: int) -> str:
    r"""Return the character at ``(r, c)``; off the grid reads as water."""
    if r < 0 or r >= len(grid) or c < 0 or c >= len(grid[0]):
        return "~"
    return grid[r][c]


def _open(grid: Sequence[str], r: int, c: int) -> bool:
    r"""Whether a cod can swim into ``(r, c)``."""
    return _cell(grid, r, c) != "~"


def _open_dirs(
    grid: Sequence[str], r: int, c: int, exclude: _Direction | None = None
) -> list[_Direction]:
    r"""Return the headings out of ``(r, c)`` that are not water."""
    return [
        d
        for d, (dr, dc) in _DIRS.items()
        if d != exclude and _open(grid, r + dr, c + dc)
    ]


# : What one cod's step wants.
# : the input port.
# : list -- Eval's shape, for.
@dataclass(frozen=True)
class _Print:
    r"""Write a cod's value."""

    value: int


@dataclass(frozen=True)
class _Read:
    r"""Take a number; the cod that asked is at ``index`` in the new list."""

    index: int


type _Effect = _Print | _Read

# : Every value a COD tick can.
# : Each cod is frozen and a.
# : collection is a value too.
#: the shell.
type _State = tuple[_Cod, ...]

# : One instant as the.
# : ``None`` for a start marker.
type _BranchState = tuple[_Cod, ...] | None

# : The most outcomes one tick.
# : once per blocked cod, so.
# : grows with the school.
# : random languages' caps this.
# : caller's remaining budget:.
# : which would make the same.
#: tick was reached.
_TICK_FANOUT = 256


def _step_cod(
    cod: _Cod,
    grid: Sequence[str],
    dashes: AbstractSet[tuple[int, int]],
    dots: AbstractSet[tuple[int, int]],
    turn: int | None,
) -> tuple[list[_Cod], list[_Effect]]:
    r"""Return the cods that follow ``cod``, and what it wants done."""
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
    r"""Per-run COD state: the grid and every live cod."""

    # : The seed a reproducible run.
    # : language, not to whoever is.
    # : junction example East, the.
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

        cods: list[_Cod] = []
        started = False
        # : The start cell and the.
        # : when there was a real.
        # : draw itself; one open.
        # : ``None`` and the search.
        self._launch: tuple[int, int, tuple[_Direction, ...]] | None = None
        for r, row in enumerate(self.grid):
            for c, ch in enumerate(row):
                if ch == ">":
                    if started:
                        raise ValueError("multiple cod start markers")
                    started = True
                    opens = self._open_dirs(r, c)
                    if not opens:
                        raise ValueError("cod start is fully enclosed")
                    if len(opens) > 1:
                        self._launch = (r, c, tuple(opens))
                    d = opens[0] if len(opens) == 1 else self._choose(opens)
                    cods.append(_Cod(r, c, d, 0))
        if not started:
            raise ValueError("no cod start marker '>'")
        self.cods: _State = tuple(cods)

    # -- geometry.

    def _open_dirs(
        self, r: int, c: int, exclude: _Direction | None = None
    ) -> list[_Direction]:
        return _open_dirs(self.grid, r, c, exclude)

    def _choose(self, options: list[_Direction]) -> _Direction:
        return options[draw(self._rng, len(options))]

    # -- state.

    @property
    def halted(self) -> bool:
        return not self.cods

    # The VM's language-shaped view.

    # : ``ip`` is a cell of the.
    # : parts are a row and a.
    # : this a caller cannot tell.
    # : stack, which look identical.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...]:
        r"""Every live cod's ``(row, col, heading, value)``, flattened."""
        order = list(_DIRS)
        cods = sorted(
            (cod.r, cod.c, order.index(cod.d), cod.value) for cod in self.cods
        )
        return tuple(v for cod in cods for v in cod)

    @property
    def memory(self) -> list[int]:
        r"""Each live cod's carried value."""
        return [cod.value for cod in self.cods]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (
            tuple(sorted((cod.r, cod.c, cod.d, cod.value) for cod in self.cods)),
            self.io.position(),
        )

    # The all-random-outcomes.
    # nothing else -- the grid and.
    # branching state is that.
    # carries: a read declines.

    def branching_snapshot(self) -> _BranchState:
        r"""Return the pre-launch start state for a branching search."""
        return None if self._launch else self.cods

    def branching_halted(self, state: object) -> bool:
        r"""Report whether ``state`` has no cod left."""
        cods = cast(_BranchState, state)
        return cods is not None and not cods

    def branching_successors(
        self, state: object, _limit: int
    ) -> tuple[_BranchState, ...] | None:
        r"""Return the state for every draw this tick could make."""
        cods = cast(_BranchState, state)
        if cods is None:
            launch = self._launch
            if launch is None:  # pragma: no cover - snapshot pairs the two
                # ``branching_snapshot``.
                # ``_launch`` is set, so the.
                # cannot fire.
                # because an assert is compiled.
                # would turn the contradiction.
                # three lines further on.
                raise AssertionError("a pre-launch state must carry a launch")
            row, col, opens = launch
            return tuple((_Cod(row, col, d, 0),) for d in opens)

        frontier: list[tuple[_Cod, ...]] = [()]
        for cod in cods:
            turns: tuple[int | None, ...] = (None,)
            ahead = (cod.r + _DIRS[cod.d][0], cod.c + _DIRS[cod.d][1])
            if not _open(self.grid, *ahead):
                alts = _open_dirs(self.grid, cod.r, cod.c, exclude=_OPP[cod.d])
                if len(alts) > 1:
                    turns = tuple(range(len(alts)))

            grown_by_turn: list[tuple[_Cod, ...]] = []
            for turn in turns:
                grown, effects = _step_cod(
                    cod, self.grid, self._edge_dashes, self._edge_dots, turn
                )
                if any(not isinstance(effect, _Print) for effect in effects):
                    return None
                grown_by_turn.append(tuple(grown))

            if len(frontier) * len(grown_by_turn) > _TICK_FANOUT:
                raise TimeoutError(
                    f"undecided: one COD tick exceeds the {_TICK_FANOUT}-outcome "
                    "cap on a single transition"
                )
            frontier = [
                (*partial, *grown) for partial in frontier for grown in grown_by_turn
            ]
        return tuple(frontier)

    @property
    def _state(self) -> _State:
        r"""The complete changing state at a cod-tick boundary."""
        return self.cods

    def _restore(self, state: _State) -> None:
        r"""Write a tick transition back onto the machine shell."""
        self.cods = state

    # -- stepping.

    def step(self) -> None:
        r"""Advance every live cod by one cell, executing what it lands on."""
        state = self._state
        if not state:
            return
        next_cods: list[_Cod] = []
        remaining = state
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
                    # The cod has already swum onto.
                    # reads, and the original left.
                    # raised at EOF -- so commit.
                    self._restore((*next_cods, *grown, *remaining[index + 1 :]))
                    read = self.io.input_num()
                    grown = [
                        _Cod(k.r, k.c, k.d, read) if i == effect.index else k
                        for i, k in enumerate(grown)
                    ]
            next_cods.extend(grown)
        self._restore(tuple(next_cods))


def run(code: str, io: IO, rng: Randomness | None = None) -> None:
    r"""Run a COD program until no cod remains."""
    machine = _Machine(code, io, rng=rng)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
