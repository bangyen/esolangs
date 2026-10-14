"""Interpreter for Streetcode.

A car drives a 2D network of two-way, two-character-wide streets, running
the instruction under it at every cell; memory is an unbounded list of
signed integer cells under an unsigned cell pointer (CP).

The author's Streetcode revision 78016 specifies right-hand driving and
leftmost/second-leftmost junction choices. Multi-stage merge timing is
an implementation convention corroborated by the wiki examples.  The page
gives no geometry, so these are readings: the car starts on the first of
N, E, S, W with a wall to its right and road ahead (``C`` at a ring's
corner heads down the side road, not into the turn); a dead end turns the
car across the street in two steps, and a ``U`` on the cell where that
turn lands does not reverse it again.

Errors: a malformed program (:mod:`.validation`) raises :class:`ValueError` at
construction (streets two wide, road enclosed, wall forms, no ``-`` beside ``|``, one
network, exactly one ``C``); a ``U`` with no opposite lane raises
:class:`~esolangs.exceptions.HaltError`.  ``_`` at cell 0 raises ``HaltError``:
the wiki says "The CP is unsigned and right-unbounded", so no cell lies
left of 0, and an abort beats a wrong answer.  ``O`` on a non-code-point
raises ``HaltError``.  ``I`` on exhausted input raises :class:`EOFError`; a
newline stores character code 10.  ``I``/``O``'s "Nth register" is the
CPth cell.  The wiki's Turing-completeness sentence names ``<`` and ``>``;
the command table's ``=``/``_`` move CP, and ``<``/``>`` are nops.
"""

import functools
from collections.abc import Mapping
from types import MappingProxyType
from typing import Self, assert_never

from esolangs.exceptions import HaltError
from esolangs.languages.streetcode.interpreter.geometry import (
    _NO_LATCHES,
    _drive,
    _Grid,
    _Heading,
    _initial_heading,
    _Op,
    _State,
)
from esolangs.languages.streetcode.interpreter.validation import (
    _Edges,
    validate_street,
)
from esolangs.runtime._drive import drive
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

#: The whole of a run the pure transition owns: the car, the cell pointer,
#: the sparse tape, and whether the car has halted.  A tuple of values, so a
#: snapshot and the transition can pass one around without aliasing a live
#: machine field.
type _Run = tuple[_State, int, Mapping[int, int], bool]


def _frozen(
    car: _State, pointer: int, tape: Mapping[int, int], *, halted: bool
) -> _Run:
    """Rebuild the immutable run value from one step's mutable tape."""
    return (car, pointer, MappingProxyType(tape), halted)


def _cell(cells: Mapping[int, int], pointer: int) -> int:
    """Return the cell under ``pointer``; never-written cells read as 0."""
    return cells.get(pointer, 0)


def _execute(op: _Op, cp: int, cells: dict[int, int], value: int | None) -> int:
    """Run one tape instruction on ``cells`` in place; return the new CP.

    ``HALT`` and ``TURN`` never get here: :func:`_advance` owns them.
    """
    match op:
        case "INC":
            cells[cp] = _cell(cells, cp) + 1
        case "DEC":
            cells[cp] = _cell(cells, cp) - 1
        case "RIGHT":
            cp += 1
        case "LEFT":
            if not cp:
                raise HaltError(
                    "'_' at cell 0 would move the unsigned CP below zero",
                    hint="move right with '=' before moving left with '_'",
                )
            cp -= 1
        case "IN":
            if value is None:
                raise HaltError(
                    "input transition requires a value",
                    hint="read the character before applying the input transition",
                )
            cells[cp] = value
        case "OUT":
            try:
                chr(_cell(cells, cp))
            except ValueError:
                raise HaltError(
                    hint="keep character output values between 0 and 1114111"
                ) from None
            # The car still drives; the character is the caller's to write.
        case "NOP":
            # ``C``, space and every undefined character fold to NOP (see
            # ``_Op``).
            pass
        case "HALT" | "TURN":
            raise AssertionError(f"{op} is handled by _advance")
        case _:
            # Unreachable, and checked to be: ``_Op`` is exhausted by the
            # arms above, so this is the checker's exhaustiveness proof.
            assert_never(op)
    return cp


def _u_turn(grid: _Grid, state: _State, arrival_cell: int) -> _State:
    """Return the state a ``U`` turns the car into, or raise ``HaltError``."""
    turned = _drive(grid, state, arrival_cell, arrival_cell)
    if turned is None or turned == "halt":
        raise HaltError(
            f"a U-turn at {arrival_cell} has nowhere to end: the "
            f"street has no opposite lane, which is narrower than "
            f"the spec allows",
            hint="widen the street so a U-turn has an opposite lane",
        )
    return turned


# Movement is pure and lives in :mod:`.geometry`; the run itself is the pure
# :func:`_advance`, which takes the whole run and the one input value a step needs and
# returns the next run and any character to print.  :class:`_Machine` is the shell that
# reads and writes.  :func:`_drive` is the whole of movement in one signature,
# ``_drive(grid, state, arrival_cell, current_cell)``, which lets
# :func:`.validation.drive_states` enumerate the state space.
def _advance(
    run: _Run,
    grid: _Grid,
    graph: dict[_State, _Edges] | None,
    value: int | None = None,
) -> tuple[_Run, int | None]:
    """Return the run after one cell, and the character ``O`` prints, if any.

    Pure: the grid and the drive-state graph are constants of the run, the
    input character arrives already read as ``value``, and output is
    returned rather than written.  The tape and the car are rebuilt, never
    edited, so the state handed in is untouched.
    """
    state, cp, cells, done = run
    if done:
        return run, None
    # A private, mutable copy: the immutable mapping handed in is never
    # touched, and every return re-freezes what this step built.
    cells = dict(cells)

    op = grid.op_at(state.row, state.col)
    if op == "HALT":
        return _frozen(state, cp, cells, halted=True), None

    # The cell on arrival, before this square's instruction, so a turning
    # square's ``=`` sets up the road ahead without deciding it.
    arrival_cell = _cell(cells, cp)

    if op == "TURN":
        return _frozen(_u_turn(grid, state, arrival_cell), cp, cells, halted=done), None
    cp = _execute(op, cp, cells, value)

    current_cell = _cell(cells, cp)
    edges = None if graph is None else graph.get(state)
    successor = (
        _drive(grid, state, arrival_cell, current_cell)
        if edges is None
        else edges[int(arrival_cell != 0), int(current_cell != 0)]
    )

    output = current_cell if op == "OUT" else None

    if successor == "halt":
        return _frozen(state, cp, cells, halted=True), output
    if successor is None:
        if edges is None:
            return _frozen(state, cp, cells, halted=True), output
        raise AssertionError(
            f"no successor for {(state.row, state.col)} heading"
            f" {state.heading}: the drive-state graph outlived"
            " the totality check"
        )
    return _frozen(successor, cp, cells, halted=done), output


class _Machine:
    """Per-run Streetcode shell: the car, its heading, and the cell list.

    ``step`` is the shell: it reads the one input character an ``I`` cell
    needs, hands the run to the pure :func:`_advance`, stores the run that
    comes back, and writes any character an ``O`` cell produced.  ``halted``
    is true once ``;`` runs or the car has nowhere to go.
    """

    def __init__(
        self,
        code: list[str],
        io: IO,
        *,
        _compiled: tuple[_Grid, _State, dict[_State, _Edges] | None] | None = None,
    ) -> None:
        """Locate the single ``C`` and derive the car's initial heading.

        ``_compiled`` is the geometry a cached prototype already validated
        for identical code -- grid, start state and drive graph -- so this
        machine skips revalidating and re-searching it.
        """
        if not code or not any(line.strip() for line in code):
            raise syntax_error(
                "Streetcode program cannot be empty",
                "draw an enclosed two-cell-wide street containing one C",
            )
        self.io = io
        if _compiled is not None:
            self.grid, self._state, self._graph = _compiled
        else:
            self.grid = _Grid(code)
            starts = [
                (r, c)
                for r, row in enumerate(self.grid)
                for c, ch in enumerate(row)
                if ch == "C"
            ]
            if len(starts) != 1:
                raise syntax_error(
                    f"Streetcode program must have exactly one C, found {len(starts)}",
                    "keep exactly one C on the street as the car start",
                )
            # The whole of the machine's steering state, in the one record the
            # movement rules speak in.  ``step`` hands it to :func:`_drive` and
            # stores back what comes out, so the value looked up in the
            # drive-state graph is the machine's own.  See :class:`_Latches`
            # for what the three latches carry.
            self._state = _State(
                *starts[0], _initial_heading(self.grid, starts[0]), _NO_LATCHES
            )
            # The enumerated drive-state graph, or ``None`` for a program whose
            # geometry is not a street or whose validation a fixture patched
            # out.  ``step`` then calls :func:`_drive` directly -- the same
            # function that filled the graph, so the answer is the same.
            self._graph = None
            # Last, because ``_validate_total`` drives the real movement rules
            # over the grid and so needs every field they touch to exist.
            self._validate(starts[0])
        self.cp = 0
        # The tape, as a value: an instruction returns the cells that
        # follow rather than writing into a dict.  It is bounded by how far
        # CP has travelled, which grows one cell at a time, so rebuilding
        # it per write is a constant.
        self.cells: Mapping[int, int] = {}
        self._done = False
        self._input_reads = 0

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
            self.io.progress(),
            self._done,
            self._input_reads,
            tuple(self.grid),
        )

    def _validate(self, start: tuple[int, int]) -> None:
        """Validate the street and keep its drive-state graph.

        The one hook the wall-shape fixtures disable; the checks are in
        :mod:`.validation`.
        """
        self._graph = validate_street(self.grid, start)

    def step(self) -> None:
        """Execute the cell under the car, then drive it one cell further.

        The shell: it reads the one input character an ``I`` cell needs and
        writes the one an ``O`` cell produces, then hands the values to
        :func:`_advance` and stores the run it returns.
        """
        if self._done:
            return
        op = self.grid.op_at(self.row, self.col)
        value = None
        if op == "IN":
            value = self.io.input_char()
            self._input_reads += 1
        (self._state, self.cp, frozen, self._done), output = _advance(
            (self._state, self.cp, MappingProxyType(self.cells), self._done),
            self.grid,
            self._graph,
            value,
        )
        self.cells = dict(frozen)
        if output is not None:
            self.io.print_char(chr(output))

    @staticmethod
    @functools.lru_cache(maxsize=16)
    def _compile(
        code: tuple[str, ...],
    ) -> tuple[_Grid, _State, dict[_State, _Edges] | None]:
        prototype = _Machine(list(code), IO())
        return prototype.grid, prototype._state, prototype._graph

    @classmethod
    def _for_run(cls, code: list[str], io: IO) -> Self:
        """Build a machine reusing the cached, already-validated street.

        Construction goes through :meth:`__init__` like any other machine;
        the cached tuple only skips revalidating identical geometry.
        """
        return cls(list(code), io, _compiled=cls._compile(tuple(code)))


def run(code: list[str], io: IO) -> None:
    """Drive a Streetcode car over ``code`` until it halts."""
    machine = _Machine._for_run(code, io)  # noqa: SLF001
    drive(machine)
