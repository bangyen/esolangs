"""Interpreter for Streetcode.

A car drives a 2D network of two-way, two-character-wide streets, running
the instruction under it at every cell; memory is an unbounded list of
signed integer cells under an unsigned cell pointer (CP).

``the implementation`` is the spec of record: the `wiki page
<https://esolangs.org/wiki/Streetcode>`_ never spells out "drive on the
right-hand side" or its leftmost/second-leftmost "ambiguous turn" rule, so
the movement interpretation lives there with the wiki examples
corroborating each rule.

Movement is pure and lives in :mod:`._streetcode_geometry`; the mutable run
lives in :class:`_Machine`.  :func:`_drive` is the whole of movement in one
signature, ``_drive(grid, state, arrival_cell, current_cell)``, which lets
:meth:`_Machine._drive_states` enumerate the state space.

Errors: a malformed program raises :class:`ValueError` at construction
(streets two wide, road enclosed, wall forms, no ``-`` beside ``|``, one
network, exactly one ``C``); a ``U`` with no opposite lane raises
:class:`~esolangs.exceptions.HaltError`.  ``_`` at cell 0 clamps (the wiki
says nothing; brainfuck clamps ``<``); ``O`` on a non-code-point raises
``HaltError``.  ``I`` on exhausted input raises :class:`EOFError`; an
empty line sets the cell to 0.
"""

import functools
import sys
from collections.abc import Mapping
from typing import Literal, Self, assert_never

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _DELTA,
    _NO_LATCHES,
    _WALL_FORMS,
    _WALLS,
    _drive,
    _drives_on_the_right,
    _Grid,
    _Heading,
    _initial_heading,
    _matches,
    _ReachableCell,
    _require,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _VOID as _VOID,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _Car as _Car,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _choose_heading as _choose_heading,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _crossing_mouth as _crossing_mouth,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _junction_choices as _junction_choices,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _junction_kind as _junction_kind,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _junction_shape as _junction_shape,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _lane_bounded as _lane_bounded,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _Latches as _Latches,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _lawful_turn as _lawful_turn,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _left as _left,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _Merge as _Merge,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _open_toward as _open_toward,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _plus_dist as _plus_dist,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _right as _right,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _road_mouth as _road_mouth,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _rotate as _rotate,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _rotations as _rotations,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _State as _GeometryState,
)
from esolangs.interpreters.grid_based._streetcode_geometry import (
    _turn_of as _turn_of,
)
from esolangs.interpreters.io import IO


class _State(_GeometryState):
    """The geometry state under the interpreter module's VM convention."""


type _Edges = dict[tuple[int, int], _State | Literal["halt"] | None]


class _Machine:
    """Per-run Streetcode state: the car, its heading, and the cell list.

    ``step()`` runs the cell under the car, then drives one cell by the
    rules in ``the implementation``; ``halted`` once ``;`` runs or the car
    has nowhere to go.  The only mutable thing in the module: the rules
    return a new :class:`_State`, and ``step`` stores what comes back.
    """

    def __init__(self, code: list[str], io: IO) -> None:
        """Locate the single ``C`` and derive the car's initial heading."""
        if not code or not any(line.strip() for line in code):
            raise ValueError("Streetcode program cannot be empty")
        self.io = io
        self.grid = _Grid(code)

        starts = [
            (r, c)
            for r, row in enumerate(self.grid)
            for c, ch in enumerate(row)
            if ch == "C"
        ]
        if len(starts) != 1:
            raise ValueError(
                f"Streetcode program must have exactly one C, found {len(starts)}"
            )
        # The whole of the machine's steering state, in the one record the
        # movement rules speak in.  ``step`` hands it to :func:`_drive` and
        # stores back what comes out, so the value looked up in the
        # drive-state graph is the machine's own.  See :class:`_Latches`
        # for what the three latches carry.
        self._state = _State(
            *starts[0], _initial_heading(self.grid, starts[0]), _NO_LATCHES
        )
        self.cp = 0
        # The tape, as a value: an instruction returns the cells that
        # follow rather than writing into a dict.  It is bounded by how far
        # CP has travelled, which grows one cell at a time, so rebuilding
        # it per write is a constant.
        self.cells: Mapping[int, int] = {}
        self._done = False
        # The enumerated drive-state graph, or ``None`` for a program whose
        # geometry is not a street or whose validation a fixture patched
        # out.  ``step`` then calls :func:`_drive` directly -- the same
        # function that filled the graph, so the answer is the same.
        self._graph: dict[_State, _Edges] | None = None
        # Last, because ``_validate_total`` drives the real movement rules
        # over the grid and so needs every field they touch to exist.
        self._validate(starts[0])

    @property
    def halted(self) -> bool:
        """Whether the car has halted."""
        return self._done

    # The VM's language-shaped view.

    #: The first two parts of ``ip`` are a row and a column, the rest a
    #: heading.  Without this a caller cannot tell the pair from a call
    #: depth or a frame stack, which look identical.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...]:
        """The car's ``(row, col, heading)``, heading as its index in ``NESW``."""
        return (self.row, self.col, "NESW".index(self.heading))

    @property
    def memory(self) -> list[int]:
        """The tape's cells, densified up to the highest cell touched."""
        cells = self.cells
        if not cells:
            return []
        return [cells.get(i, 0) for i in range(max(cells) + 1)]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    # Read-only views onto the one record that holds the car: a caller
    # that wants to *move* it states the whole position at once through
    # :meth:`place`, so the three coordinates cannot come from two places.

    @property
    def row(self) -> int:
        """The row the car occupies."""
        return self._state.row

    @property
    def col(self) -> int:
        """The column the car occupies."""
        return self._state.col

    @property
    def heading(self) -> _Heading:
        """The direction the car points."""
        return self._state.heading

    def place(self, row: int, col: int, heading: _Heading) -> None:
        """Put the car at ``(row, col)`` pointing ``heading``.

        For fixtures that drive from somewhere other than ``C``.  Latches
        are left alone: a test placing a car *and* setting up a merge wants both.
        """
        self._state = self._state._replace(row=row, col=col, heading=heading)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        ``_done`` matters: ``;`` halts without moving, so without it the
        halt looks like a repeat of the step before.
        """
        return (
            self._state,
            self.cp,
            tuple(sorted(self.cells.items())),
            self.io.position(),
            self._done,
        )

    def _cell(self) -> int:
        """Return the CPth cell's value, defaulting to 0 if untouched."""
        return self.cells.get(self.cp, 0)

    def _set_cell(self, value: int) -> None:
        """Write the CPth cell, replacing the tape rather than editing it."""
        self.cells = {**self.cells, self.cp: value}

    def _block(self, cell: _ReachableCell) -> tuple[str, ...]:
        """Return the three-by-three neighbourhood around a reachable cell.

        Not bounds-checked: :meth:`_validate_enclosed` has rejected any
        road touching the border, and the precondition states that.
        """
        row, col = cell
        _require(
            condition=0 < row < self.grid.height - 1 and 0 < col < self.grid.width - 1,
            message=(
                f"{cell} is on the border of the grid, so its neighbourhood"
                " runs off it: the enclosure check did not establish what"
                " this read depends on"
            ),
        )
        return tuple(
            self.grid[row + d_row, col + d_col]
            for d_row in (-1, 0, 1)
            for d_col in (-1, 0, 1)
        )

    def _validate(self, start: tuple[int, int]) -> None:
        """Reject a malformed street network before the car moves.

        :meth:`_validate_width` and :meth:`_validate_walls` over the cells
        reachable from ``C``; the one hook the wall-shape fixtures disable.
        """
        reachable = self._validate_width(start)
        if reachable is not None:
            self._validate_enclosed(reachable)
            self._validate_walls(reachable)
            self._validate_glyphs()
            self._validate_connected(reachable)
            self._validate_total(start)

    def _drive_states(self, start: tuple[int, int]) -> dict[_State, _Edges]:
        """Explore every driving state the car can reach from ``start``.

        Kept as ``_graph`` for :meth:`_validate_total` and :meth:`step`.
        A state is position, heading and latches; geometry is static, so
        the BFS terminates.  Movement reads the tape at exactly two places,
        both testing ``== 0`` (:func:`_heading_from_merge_target` on the
        arrival cell, :func:`_heading_from_junction` on the current one),
        so probing all four bit combinations is exhaustive, not a sample.
        A ``None`` successor is a state the car cannot leave.
        """
        origin = _State(*start, _initial_heading(self.grid, start), _NO_LATCHES)
        graph: dict[_State, _Edges] = {origin: {}}
        pending = [origin]
        while pending:
            state = pending.pop()
            edges = graph[state]
            for arrival in (0, 1):
                for current in (0, 1):
                    successor = _drive(self.grid, state, arrival, current)
                    edges[arrival, current] = successor
                    if (
                        successor is not None
                        and successor != "halt"
                        and successor not in graph
                        and _drives_on_the_right(self.grid, successor)
                    ):
                        graph[successor] = {}
                        pending.append(successor)
        return graph

    def _validate_total(self, start: tuple[int, int]) -> None:
        """Reject a street the car can drive into and not out of.

        Only ``;`` halts a well-formed program, so a reachable state with
        no successor is a wedged street, named here.  Hugging is total by
        construction, so today this rejects only a reachable ``U`` with a
        walled opposite lane (``HaltError`` promoted to ``ValueError``);
        137472 small walled grids found none only this check rejects.
        """
        self._graph = self._drive_states(start)
        for state, edges in self._graph.items():
            # ``;`` reports ``"halt"`` rather than ``None``, so ``None``
            # means only the one thing.
            if any(successor is None for successor in edges.values()):
                raise ValueError(
                    f"the car cannot drive out of {(state.row, state.col)} heading"
                    f" {state.heading}: the street is a dead end with no ';'"
                )
            self._check_state_invariants(state, edges)

    def _check_state_invariants(self, state: _State, edges: _Edges) -> None:
        """Assert what must hold of a drive state under any reading of the spec.

        A car inside a wall, or one that teleports, is wrong under every
        reading (a junction firing a cell early once drove the car inside
        the wall).  :class:`AssertionError`, not ``ValueError``: a breach is
        the movement rules disagreeing with the grid.
        """
        if not self.grid.open_at(state.row, state.col):
            raise AssertionError(
                f"the car occupies {(state.row, state.col)}, which is not"
                f" open floor: {self.grid[state.row, state.col]!r}"
            )
        for successor in edges.values():
            if successor is None or successor == "halt":
                continue
            # A step drives one cell along one axis.  Anything else is the
            # car teleporting, which no movement rule is allowed to do.
            steps = abs(successor.row - state.row) + abs(successor.col - state.col)
            if steps != 1:
                raise AssertionError(
                    f"the car moved from {(state.row, state.col)} to"
                    f" {(successor.row, successor.col)}, which is not one"
                    " orthogonal step"
                )
            if not self.grid.open_at(successor.row, successor.col):
                raise AssertionError(
                    f"the car drove from {(state.row, state.col)} into"
                    f" {(successor.row, successor.col)}, which is not open"
                    f" floor: {self.grid[successor.row, successor.col]!r}"
                )
        merge = state.latches.merge
        # A latch whose heading no longer matches is abandoned on the next
        # step, so its target is stale and describes no geometry.
        if merge is None or state.heading != merge.latched_heading:
            return
        if not self.grid.open_at(merge.target_row, merge.target_col):
            raise AssertionError(
                f"the merge latched at {(state.row, state.col)} is driving to"
                f" {merge.target}, which is not open floor:"
                f" {self.grid[merge.target_row, merge.target_col]!r}"
            )
        # The approach does not change lane, so the target sits straight
        # ahead along the latched heading -- never to one side, never
        # behind a car that can only drive forwards onto it.
        d_row, d_col = _DELTA[merge.latched_heading]
        off_row, off_col = merge.target_row - state.row, merge.target_col - state.col
        if off_row * d_col - off_col * d_row != 0:
            raise AssertionError(
                f"the merge latched at {(state.row, state.col)} heading"
                f" {merge.latched_heading} is driving to {merge.target}, which"
                " is off the axis it is travelling along"
            )
        if off_row * d_row + off_col * d_col < 0:
            raise AssertionError(
                f"the merge latched at {(state.row, state.col)} heading"
                f" {merge.latched_heading} is driving to {merge.target}, which"
                " is behind it"
            )

    def _validate_width(self, start: tuple[int, int]) -> set[_ReachableCell] | None:
        """Validate that every street is two characters wide.

        A corridor cell with open neighbours directly opposite, or a dead
        end, must have an open perpendicular neighbour; isolated cells and
        wall-free grids are exempt, and a blank row is a lane.  The upper
        bound is a fully open 3x3 block, which a two-wide network never
        contains (a cross-section run through a crossing reports the other
        street's length).  A 3x2 room passes, deliberately.
        """
        # No walls → not a street network (e.g. ["C","U"] or ["C"])
        if not any(ch in _WALLS for row in self.grid for ch in row):
            return None
        # BFS reachable open cells from C (open = not a wall)
        from collections import deque

        sr, sc = start
        visited: set[_ReachableCell] = set()
        q: deque[_ReachableCell] = deque([_ReachableCell((sr, sc))])
        visited.add(_ReachableCell((sr, sc)))
        while q:
            r, c = q.popleft()
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                # No bounds test: off the grid is not open, so the fill
                # cannot walk out of the drawing.
                if self.grid.open_at(nr, nc) and (nr, nc) not in visited:
                    visited.add(_ReachableCell((nr, nc)))
                    q.append(_ReachableCell((nr, nc)))
        # Isolated single cell is not a street
        if len(visited) <= 1:
            return None
        violation = self._width_violation(visited)
        if violation is not None:
            raise ValueError(violation)
        return visited

    def _width_violation(self, reachable: set[_ReachableCell]) -> str | None:
        """Name a cell breaking the two-wide rule, or ``None`` if none does.

        The rule as a value, so it can be asked without a second implementation.
        """
        for r, c in reachable:
            n = self.grid.open_at(r - 1, c)
            s = self.grid.open_at(r + 1, c)
            e = self.grid.open_at(r, c + 1)
            w2 = self.grid.open_at(r, c - 1)
            cnt = sum((n, s, e, w2))
            if cnt == 1:
                return f"not two-wide at {(r, c)} (dead end)"
            if n and s and not (e or w2):
                return f"not two-wide at {(r, c)} (vertical)"
            if e and w2 and not (n or s):
                return f"not two-wide at {(r, c)} (horizontal)"
            if all(
                self.grid.open_at(r + dr, c + dc)
                for dr in (0, 1, 2)
                for dc in (0, 1, 2)
            ):
                return f"not two-wide at {(r, c)} (wider than two)"
        return None

    def _validate_walls(self, reachable: set[_ReachableCell]) -> None:
        """Validate the wall structure around every drivable cell.

        Width misses a one-cell hole (``-- --``); each reachable cell's 3x3
        must match ``_WALL_FORMS`` up to rotation.  The forms let a wall
        simply stop and admit any wall character at a corner -- whether a
        divider must end in ``+`` is unsettled, and
        ``tests/fixtures/streetcode_hello.txt`` leaves its ends bare.
        Must run after :meth:`_validate_enclosed`: :meth:`_block` does not
        bounds-check.
        """
        for cell in reachable:
            r, c = cell
            block = self._block(cell)
            # A street is two cells wide, so every reachable cell has a
            # wall within one; a wall-free neighbourhood is an interior
            # wider than two, already rejected by the width check.
            if not any(ch in _WALLS for ch in block):  # pragma: no cover
                continue
            # The two-wide check runs first and rejects every malformed
            # shape found so far; this stands as the independent check the
            # forms were written to be.
            if not any(  # pragma: no cover - the width check rejects these first
                _matches(block, form) for form in _WALL_FORMS
            ):
                shape = " ".join(
                    "".join("." if ch not in _WALLS else ch for ch in block[i : i + 3])
                    for i in (0, 3, 6)
                )
                raise ValueError(f"malformed wall at {(r, c)} ({shape})")

    def _validate_enclosed(self, reachable: set[_ReachableCell]) -> None:
        """Reject a street that runs off the edge of the grid.

        A flood fill from ``C`` reaching the border has escaped through a
        hole.  This is what catches a two-wide hole, which is legal-width
        passage the width check cannot see.
        """
        violation = self._enclosure_violation(reachable)
        if violation is not None:
            raise ValueError(violation)

    def _enclosure_violation(self, reachable: set[_ReachableCell]) -> str | None:
        """Name a road cell on the grid's border, or ``None`` if none is.

        The property :meth:`_block` depends on, stated once.
        """
        for r, c in reachable:
            if r in (0, self.grid.height - 1) or c in (0, self.grid.width - 1):
                return (
                    f"street reaches the edge of the grid at {(r, c)}:"
                    " the road is not enclosed by walls"
                )
        return None

    def _validate_glyphs(self) -> None:
        """Reject a ``-`` and a ``|`` drawn side by side.

        A wall changing direction without its ``+``.  About glyph choice,
        not wall placement, so the forms in :meth:`_validate_walls` cannot see it.
        """
        violation = self._glyph_violation()
        if violation is not None:
            raise ValueError(violation)

    def _glyph_violation(self) -> str | None:
        """Name a ``-`` drawn beside a ``|``, or ``None`` if none is."""
        for r in range(self.grid.height):
            for c in range(self.grid.width):
                char = self.grid[r, c]
                if char == "-":
                    neighbours = ((r, c - 1), (r, c + 1))
                    other = "|"
                elif char == "|":
                    neighbours = ((r - 1, c), (r + 1, c))
                    other = "-"
                else:
                    continue
                for nr, nc in neighbours:
                    if self.grid[nr, nc] == other:
                        return (
                            f"wall turns without a corner at {(r, c)}:"
                            f" {char!r} beside {other!r} at {(nr, nc)}"
                        )
        return None

    def _validate_connected(self, reachable: set[_ReachableCell]) -> None:
        """Reject geometry that is not part of the one street network.

        Grow the reachable open cells by one so the region takes in its
        walls; anything still drawn belongs to no street.  A one-thick
        island is taken in whole; only a block with an interior falls
        outside.  Blank cells are ignored (``ljust`` padding, the boolean
        example's margins).  Strict: any character off the street, not
        only walls -- stray marks are likelier a slip than a comment.
        """
        violation = self._connection_violation(reachable)
        if violation is not None:
            raise ValueError(violation)

    def _connection_violation(self, reachable: set[_ReachableCell]) -> str | None:
        """Name drawn geometry off the street, or ``None`` if none is."""
        grown = {
            (r + dr, c + dc)
            for r, c in reachable
            for dr in (-1, 0, 1)
            for dc in (-1, 0, 1)
        }
        for r in range(self.grid.height):
            for c in range(self.grid.width):
                char = self.grid[r, c]
                if char == " " or (r, c) in grown:
                    continue
                return f"geometry not connected to the street at {(r, c)} ({char!r})"
        return None

    def step(self) -> None:
        """Execute the cell under the car, then drive it one cell further."""
        if self._done:
            return
        op = self.grid.op_at(self.row, self.col)
        if op == "HALT":
            self._done = True
            return

        # The driving state as the car arrives, for the graph lookup
        # below.  An instruction moves CP and the tape but never the car,
        # its heading or the latches, and ``U`` returns before the lookup.
        state = self._state

        # The cell on arrival, before this square's instruction, so a
        # turning square's ``=`` sets up the road ahead without deciding it.
        # Passed, not kept: it would look like snapshot state.
        arrival_cell = self._cell()

        if op == "INC":
            self._set_cell(self._cell() + 1)
        elif op == "DEC":
            self._set_cell(self._cell() - 1)
        elif op == "RIGHT":
            self.cp += 1
        elif op == "LEFT":
            # Clamped, not an error: an unsigned quantity that cannot go
            # lower saturates.  See the module docstring.
            self.cp = max(0, self.cp - 1)
        elif op == "IN":
            value = self.io.input_str()
            self._set_cell(ord(value[0]) if value else 0)
        elif op == "OUT":
            try:
                self.io.print_char(chr(self._cell()))
            except ValueError:
                raise HaltError from None
        elif op == "TURN":
            # The U-turn ends in the lane now on the right; turning in
            # place leaves the car in the oncoming lane, where the hug's
            # two right turns cancel it.  Old-heading latches are void.
            # Via :func:`_drive` so the run and the graph agree; ``None``
            # (no opposite lane) is a malformed street.
            turned = _drive(self.grid, state, arrival_cell, arrival_cell)
            if turned is None or turned == "halt":
                raise HaltError(
                    f"a U-turn at {arrival_cell} has nowhere to end: the "
                    f"street has no opposite lane, which is narrower than "
                    f"the spec allows"
                )
            self._state = turned
            return
        elif op == "NOP":
            # ``C``, space and every undefined character fold to NOP (see
            # ``_Op``).  Spelled out rather than fallen through, so the
            # ``else`` below is the checker's exhaustiveness proof.
            pass
        else:
            # Unreachable, and checked to be: a glyph added to ``_Op``
            # without an arm here fails the type check rather than
            # silently behaving as a no-op.
            assert_never(op)

        # A memo of :func:`_drive` over every reachable state, keyed on the
        # two reads' zero-ness; a miss (non-street geometry, or a state the
        # search never enumerated) falls through to :func:`_drive` itself.
        current_cell = self._cell()
        edges = None if self._graph is None else self._graph.get(state)
        successor = (
            _drive(self.grid, state, arrival_cell, current_cell)
            if edges is None
            else edges[int(arrival_cell != 0), int(current_cell != 0)]
        )

        if successor == "halt":
            self._done = True
            return
        if successor is None:
            if edges is None:
                # No graph vouched for this state, so running out of road
                # is the car's ordinary dead end: stop.
                self._done = True
                return
            # ``_validate_total`` rejects a wedged state, so reaching one
            # here means the graph and the validator disagree -- a bug in
            # this module.  Halting quietly would hand back a truncated
            # run as though it were the answer.
            raise AssertionError(
                f"no successor for {(self.row, self.col)} heading"
                f" {self.heading}: the drive-state graph outlived"
                " the totality check"
            )
        self._state = successor

    @staticmethod
    @functools.lru_cache(maxsize=16)
    def _compile(
        code: tuple[str, ...],
    ) -> tuple[_Grid, _State, dict[_State, _Edges] | None]:
        prototype = _Machine(list(code), IO())
        return prototype.grid, prototype._state, prototype._graph

    @classmethod
    def _for_run(cls, code: list[str], io: IO) -> Self:
        grid, state, graph = cls._compile(tuple(code))
        machine = cls.__new__(cls)
        machine.io = io
        machine.grid = grid
        machine._state = state  # noqa: SLF001
        machine.cp = 0
        machine.cells = {}
        machine._done = False  # noqa: SLF001
        machine._graph = graph  # noqa: SLF001
        return machine


def run(code: list[str], io: IO) -> None:
    """Drive a Streetcode car over ``code`` until it halts."""
    machine = _Machine._for_run(code, io)  # noqa: SLF001
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
