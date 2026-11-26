"""Interpreter for thisthat.

Single-line wires carry execution pointers; double-line wires carry a zero,
one, or empty transfer. Every pointer advances once per cycle, ordered by node
priority and grid position. Coincident pointers implement merges, logic, and
barriers. The run halts at ``◉`` (end of its cycle) or when no pointer is
left. ``◘`` uses the shared randomness hook, so callers may inject a
reproducible source.

Input/output:
    Input is newline-separated sets of 0 or 1 characters, other whitespace
    ignored.  A read past the end of the current set, or at EOF, sends an
    empty transfer and the run goes on.  An empty transfer into a data-mode
    ``◇`` prints nothing; it is the page's "flag", which skips the rest of the
    set and moves reads to the next.

Errors:
    ProgramError: a branch state from another program (exhaustive
        random-merge search only).
    HaltError: no ``▣`` start node; a cell outside the wire and node
        alphabets; an input character that is not 0 or 1.

Decisions:
    Readings the page leaves open, each forced by a wiki example:

    * A node that sends data in execution mode (``◇□■▦◧⬓◨⬒◹◺``) also goes on
      down its other execution wires (Kolakoski's ``▣─□─■─◹─■─◺`` chain, the
      truth machine's ``■`` loop).
    * An arrow never sends a pointer back the way it came, so it is a diode;
      without that the truth machine's ``1`` loop multiplies its pointers.  A
      white arrow passes perpendicular flow straight through (the Cat's ``▽``
      lets its end-of-input transfer by).
    * Only wires connect; touching nodes do not (Kolakoski's stacked ``⬒⬒``).
    * ``◉`` halts at the end of its cycle, so the truth machine's ``0``,
      reaching its ``◇`` in the same cycle, still prints.
    * The bistack is the quadrant of cells ``(column, row)`` from 0.  The
      cursor ``k`` sits on the diagonal and selects row ``k`` and column ``k``,
      each beginning at the axis, so they share cell ``(k, k)``.  ``◹`` always
      moves up; ``◺`` fails only at ``k = 0``.  The Cat pushes one bit per
      column, walks down until that fails, then pops row 0 in input order.
    * Sets are separated by newlines: the page says "switching to the next set
      of input" but not how; the shared example needs two (program, data).
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
from itertools import product
from math import prod
from types import MappingProxyType
from typing import Any, Literal, NamedTuple, cast

from esolangs.exceptions import HaltError
from esolangs.languages.thisthat._topology import (
    _NODES,
    _PORTS,
    _char,
    _Point,
    _router_direction,
)
from esolangs.languages.thisthat._transition import (
    _advance,
    _Cells,
    _Core,
    _FaultError,
    _head,
    _NeedDrawError,
    _NeedInputError,
    _ordered_groups,
    _Pointer,
    _Step,
    _tail,
)
from esolangs.languages.thisthat.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RandomRuntimePlan, RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._source import native_text_source
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import IO, _BufferedOutput
from esolangs.runtime.memory import format_integer
from esolangs.runtime.randomness import Randomness, draw
from esolangs.runtime.source_hints import with_hint

type _Boundary = tuple[
    tuple[_Pointer, ...],
    tuple[tuple[_Point, int], ...],
    int,
    bool,
    int,
    int,
    tuple[str, ...],
    bool,
]
type _Replay = tuple[tuple[int | None, ...], tuple[int, ...], int | tuple[int, int]]
type _State = _Boundary | tuple[*_Boundary, _Replay]


_WORKSPACE_MODEL = WorkspaceModel(
    "thisthat-v1",
    (
        "pointers",
        "cells",
        "cursor",
        "stopped",
        "input_cursor",
        "input_reads",
        "set_ended",
    ),
)


class _GridImage(NamedTuple):
    rows: tuple[str, ...]
    starts: tuple[_Pointer, ...]


def _prepare_grid(code: list[str]) -> _GridImage:
    width = max(map(len, code), default=0)
    grid = tuple(line.ljust(width) for line in code)
    starts = tuple(
        _Pointer((x, y), None)
        for y, line in enumerate(grid)
        for x, cell in enumerate(line)
        if cell == "▣"
    )
    if not starts:
        raise HaltError(
            "thisthat needs at least one start node",
            hint="add a thisthat start node to the execution graph",
        )
    unknown = {
        cell
        for line in grid
        for cell in line
        if cell != " " and cell not in _PORTS and cell not in _NODES
    }
    if unknown:
        raise HaltError(
            f"unsupported thisthat cell: {min(unknown)!r}",
            hint="use cells documented by esolangs describe --spec thisthat",
        )
    return _GridImage(grid, starts)


class _Machine:
    """thisthat shell: one immutable :data:`_Core`, rebound per cycle."""

    ip_shape = "grid"
    #: A read at EOF sends an empty transfer and the run goes on.
    eof_is_a_value = True

    def __init__(
        self,
        code: list[str] | _GridImage,
        io: IO | None = None,
        rng: Randomness | None = None,
    ) -> None:
        self.io = io if io is not None else IO()
        self.rng = rng
        image = code if isinstance(code, _GridImage) else _prepare_grid(code)
        self.grid = image.rows
        self.state: _Core = (image.starts, MappingProxyType({}), 0, False, False)
        self._input_reads = 0
        self._cycle_inputs: tuple[int | None, ...] = ()
        self._cycle_draws: tuple[int, ...] = ()
        self._cycle_output = 0
        self._writer = _BufferedOutput()

    @property
    def pointers(self) -> tuple[_Pointer, ...]:
        return self.state[0]

    @pointers.setter
    def pointers(self, value: tuple[_Pointer, ...]) -> None:
        self.state = (value, self.state[1], self.state[2], self.state[3], self.state[4])

    @property
    def cells(self) -> _Cells:
        return self.state[1]

    @cells.setter
    def cells(self, value: Mapping[tuple[int, int], int]) -> None:
        self.state = (
            self.state[0],
            MappingProxyType(dict(value)),
            self.state[2],
            self.state[3],
            self.state[4],
        )

    @property
    def cursor(self) -> int:
        return self.state[2]

    @property
    def halted(self) -> bool:
        return self.state[3] or not self.state[0]

    @property
    def ip(self) -> tuple[int, ...]:
        if not self.pointers:
            return ()
        x, y = self.pointers[0].position
        return (y, x)

    @property
    def memory(self) -> list[int]:
        return [self.cells[point] for point in sorted(self.cells)]

    @property
    def stack(self) -> list[object]:
        return [self.cursor, *sorted(self.cells.items())]

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        pointers = tuple(
            (p.position, p.previous, p.channel, p.value, p.paused)
            for p in self.state[0]
        )
        pending = self._pending_cycle()
        return _WORKSPACE_MODEL.capture(
            pointers=(
                pointers
                if pending is None
                else WorkspaceVariant("pending_cycle", (pointers, *pending))
            ),
            cells=frozenset(self.state[1].items()),
            cursor=self.state[2],
            stopped=self.state[3],
            input_cursor=self.io.progress(),
            input_reads=self._input_reads,
            set_ended=self.state[4],
        )

    def snapshot(self) -> _State:
        pointers, cells, cursor, halted, set_ended = self.state
        boundary: _Boundary = (
            pointers,
            tuple(sorted(cells.items())),
            cursor,
            halted,
            self.io.progress(),
            self._input_reads,
            self.grid,
            set_ended,
        )
        pending = self._pending_cycle()
        return boundary if pending is None else (*boundary, pending)

    def _pending_cycle(self) -> _Replay | None:
        accepted = self._writer.accepted
        written = (self._cycle_output, accepted) if accepted else self._cycle_output
        if self._cycle_inputs or self._cycle_draws or written:
            return self._cycle_inputs, self._cycle_draws, written
        return None

    def branching_snapshot(self) -> _State:
        """Return immutable state for exhaustive random-merge search."""
        return self.snapshot()

    def branching_halted(self, state: object) -> bool:
        """Report whether a branch halted or lost every pointer."""
        if not isinstance(state, tuple) or len(state) not in (8, 9):
            return False
        return bool(state[3]) or not state[0]

    def branching_successors(
        self, state: object, limit: int
    ) -> tuple[_State, ...] | None:
        """Return every random-merge successor, or ``None`` before input or a flag."""
        if not isinstance(state, tuple) or len(state) not in (8, 9):
            raise TypeError("invalid thisthat branch state")
        current: _State = state
        if self.branching_halted(current):
            if limit < 1:
                return None
            return (current,)
        boundary = cast(_Boundary, state[:8])
        replay: _Replay | None = state[8] if len(state) == 9 else None
        inputs, draws, _written = replay or ((), (), 0)
        pointers, cells, cursor, halted, progress, reads, grid, set_ended = boundary
        if grid != self.grid:
            raise ValueError("branch belongs to another thisthat program")
        if replay is None and any(
            _char(grid, pointer.position) == "◇"
            and (pointer.channel == "execution" or pointer.value is None)
            for pointer in pointers
        ):
            return None
        radices: list[int] = []
        for position, arrived in _ordered_groups(grid, pointers):
            if _char(grid, position) != "◘":
                continue
            for channel in ("execution", "data"):
                count = sum(pointer.channel == channel for pointer in arrived)
                if count > 1:
                    radices.append(count)
        remaining = radices[len(draws) :]
        branch_count = prod(remaining)
        if branch_count > limit:
            raise with_hint(
                TimeoutError(
                    f"undecided after {limit} random merges in one thisthat cycle"
                ),
                (
                    "increase the branching state/outcome limit if "
                    "feasible or reduce simultaneous random merges"
                ),
            )
        core: _Core = (
            pointers,
            MappingProxyType(dict(cells)),
            cursor,
            halted,
            set_ended,
        )
        choices = product(*(range(radix) for radix in remaining))
        successors = []
        for branch_choices in choices:
            try:
                new_core, _effects = _advance(
                    core, grid, inputs, draws=(*draws, *branch_choices)
                )
            except _NeedInputError:
                return None
            except _FaultError as fault:
                raise fault.cause from None
            new_pointers, new_cells, new_cursor, new_halted, new_ended = new_core
            successors.append(
                (
                    new_pointers,
                    tuple(sorted(new_cells.items())),
                    new_cursor,
                    new_halted,
                    progress,
                    reads,
                    grid,
                    new_ended,
                )
            )
        return tuple(successors)

    def _head(self, axis: Literal["row", "column"], value: int | None) -> int | None:
        cells, result = _head(self.cells, self.cursor, axis, value)
        self.cells = cells
        return result

    def _tail(self, axis: Literal["row", "column"], value: int | None) -> int | None:
        cells, result = _tail(self.cells, self.cursor, axis, value)
        self.cells = cells
        return result

    def _router_direction(self, cell: str, pointer: _Pointer) -> str | None:
        return _router_direction(cell, pointer)

    def _workspace(self, following: list[_Pointer]) -> _Step:
        return _Step(
            grid=self.grid,
            cells=dict(self.cells),
            cursor=self.cursor,
            inputs=(),
            draws=(),
            set_ended=self.state[4],
            following=following,
        )

    def _flush(self, effects: tuple[int, ...]) -> None:
        """Write prints beyond the accepted prefix, tracking incomplete cycles."""
        for value in effects[self._cycle_output :]:
            self._writer.write(
                self.io, format_integer(value), first=partial(self.io.print_num, value)
            )
            self._cycle_output += 1

    def step(self) -> None:
        """Execute one cycle, reading, drawing and writing as the shell.

        Each request or fault carries the prints collected before it; this
        flushes that prefix exactly once before asking for another value or
        re-raising the fault, so output order and partial output match the
        single-pass original.
        """
        if self.halted:
            return
        while True:
            try:
                core, effects = _advance(
                    self.state, self.grid, self._cycle_inputs, self._cycle_draws
                )
            except _NeedInputError as need:
                self._flush(need.effects)
                # One IO attempt per ``◇`` read, EOF included, so the port
                # sees exactly the reads the single-pass original made.
                try:
                    self._cycle_inputs = (*self._cycle_inputs, self.io.input_char())
                    self._input_reads += 1
                except EOFError:
                    self._cycle_inputs = (*self._cycle_inputs, None)
            except _NeedDrawError as need:
                self._flush(need.effects)
                self._cycle_draws = (*self._cycle_draws, draw(self.rng, need.upper))
            except _FaultError as fault:
                self._flush(fault.effects)
                raise fault.cause from None
            else:
                self._flush(effects)
                self.state = core
                if self._cycle_inputs or self._cycle_draws or self._cycle_output:
                    self._cycle_inputs = self._cycle_draws = ()
                    self._cycle_output = 0
                return


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain the prepared grid and bind invocation-owned randomness."""
    if not isinstance(source, list):
        raise TypeError("thisthat machines require split text source")
    if options.keys() - {"rng"}:
        raise TypeError("thisthat machines accept only the rng runtime option")
    image = _prepare_grid(source)
    return RandomRuntimePlan.driven(
        partial(_Machine, image), policy=CAPABILITIES.completion
    ).bind(options.get("rng"))


def _execute(
    code: list[str], io: IO, rng: Randomness | None = None
) -> CompletionReport:
    """Run a thisthat program until it halts or has no pointers left."""
    machine = _Machine(code, io, rng)
    return drive(machine, policy=CAPABILITIES.completion)


def run(code: list[str], io: IO, rng: Randomness | None = None) -> None:
    """Run a thisthat program until it halts or has no pointers left."""
    _execute(code, io, rng)


SNAPSHOT_RECORDS = (_Pointer,)


if __name__ == "__main__":
    script_main(run, shape="strip", loader=native_text_source)
