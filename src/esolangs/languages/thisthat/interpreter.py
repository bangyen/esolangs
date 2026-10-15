"""Interpreter for thisthat.

Single-line wires carry execution pointers; double-line wires carry a zero,
one, or empty transfer. Every pointer advances once per cycle, ordered by node
priority and grid position. Coincident pointers implement merges, logic, and
barriers. Readings the page leaves open, each forced by a wiki example:

- A node that sends data in execution mode (``◇□■▦◧⬓◨⬒◹◺``) also goes on
  down its other execution wires (Kolakoski's ``▣─□─■─◹─■─◺`` chain, the
  truth machine's ``■`` loop).
- An arrow never sends a pointer back the way it came, so it is a diode;
  without that the truth machine's ``1`` loop multiplies its pointers.  A
  white arrow passes perpendicular flow straight through (the Cat's ``▽``
  lets its end-of-input transfer by).
- Only wires connect; touching nodes do not (Kolakoski's stacked ``⬒⬒``).
- ``◉`` halts at the end of its cycle, so the truth machine's ``0``, reaching
  its ``◇`` in the same cycle, still prints.
- The bistack is the quadrant of cells ``(column, row)`` from 0.  The cursor
  ``k`` sits on the diagonal and selects row ``k`` and column ``k``, each
  beginning at the axis, so they share cell ``(k, k)``.  ``◹`` always moves
  up; ``◺`` fails only at ``k = 0``.  The Cat pushes one bit per column, walks
  down until that fails, then pops row 0 in input order.

- Input is newline-separated sets of 0 or 1 characters, other whitespace
  ignored.  A read past the end of the current set, or at EOF, sends an
  empty transfer.  An empty transfer into a data-mode ``◇`` prints nothing; it
  is the page's "flag", which skips the rest of the set and moves reads to the
  next.  The page says "switching to the next set of input" but not how sets
  are separated; the shared example needs two (program, data).

Malformed input, connections, or source
raise :class:`~esolangs.exceptions.HaltError`. ``◘`` uses the shared randomness
hook, so callers may inject a reproducible source. A branch from another
program is rejected with :class:`ValueError`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from itertools import product
from types import MappingProxyType
from typing import ClassVar, Literal

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.randomness import Randomness, draw
from esolangs.runtime.source_hints import with_hint

type _Point = tuple[int, int]
type _Channel = Literal["execution", "data"]

#: Each constant gate's value; ``▦`` sends nothing.
_GATE_VALUE: dict[str, int | None] = {"□": 0, "■": 1, "▦": None}

_STEP = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}
_OPPOSITE = {"E": "W", "W": "E", "N": "S", "S": "N"}
_DIRECTION = {step: name for name, step in _STEP.items()}
_PORTS = {
    "─": "EW",
    "│": "NS",
    "┌": "ES",
    "┐": "WS",
    "└": "EN",
    "┘": "WN",
    "├": "ENS",
    "┤": "WNS",
    "┬": "EWS",
    "┴": "EWN",
    "┼": "EWNS",
    "═": "EW",
    "║": "NS",
    "╔": "ES",
    "╗": "WS",
    "╚": "EN",
    "╝": "WN",
    "╠": "ENS",
    "╣": "WNS",
    "╦": "EWS",
    "╩": "EWN",
    "╬": "EWNS",
}
_SINGLE = frozenset("─│┌┐└┘├┤┬┴┼")
_DOUBLE = frozenset("═║╔╗╚╝╠╣╦╩╬")
_ARROWS = frozenset("▲▶▼◀△▷▽◁")
_NODES = frozenset("▣◉◘▲▶▼◀△▷▽◁◯◔◈◇◧⬓◨⬒◹◺◐◑◒◓□■▦")
_PRIORITY = {"◘": 2, "◈": 2, "◹": 2, "◺": 2, "◇": 3, "◧": 3, "⬓": 3, "◨": 3, "⬒": 3}
_ARROW_DIRECTION = dict(zip("▶◀▲▼▷◁△▽", "EWNSEWNS", strict=True))
_BLACK_SIDE = {"◐": "W", "◑": "E", "◒": "S", "◓": "N"}
_WHITE_SIDE = {node: _OPPOSITE[side] for node, side in _BLACK_SIDE.items()}


@dataclass(frozen=True)
class _Pointer:
    position: _Point
    previous: _Point | None
    channel: _Channel = "execution"
    value: int | None = None
    paused: bool = False


type _Cells = Mapping[tuple[int, int], int]
type _Core = tuple[tuple[_Pointer, ...], _Cells, int, bool, bool]
type _State = tuple[
    tuple[_Pointer, ...],
    tuple[tuple[_Point, int], ...],
    int,
    bool,
    int,
    int,
    tuple[str, ...],
    bool,
]


class _StepError(Exception):
    """Base for signals that pause a pure transition so the shell can answer.

    ``effects`` is the immutable prefix of prints the transition already
    produced; the shell flushes it before answering the signal.
    """

    def __init__(self, effects: tuple[int, ...] = ()) -> None:
        super().__init__(effects)
        self.effects = effects


class _NeedInputError(_StepError):
    """The transition needs one more input character to finish its step."""


class _NeedDrawError(_StepError):
    """The transition needs one more random draw to finish its step."""

    def __init__(self, upper: int = 0, effects: tuple[int, ...] = ()) -> None:
        super().__init__(effects)
        self.upper = upper


class _FaultError(_StepError):
    """A transition fault carrying the prints produced before it.

    The shell flushes ``effects`` and re-raises ``cause``, so output that
    preceded the fault survives exactly as it did before the retry kernel.
    """

    def __init__(self, cause: BaseException, effects: tuple[int, ...]) -> None:
        super().__init__(effects)
        self.cause = cause


def _char(grid: tuple[str, ...], point: _Point) -> str:
    x, y = point
    if 0 <= y < len(grid) and 0 <= x < len(grid[y]):
        return grid[y][x]
    return " "


def _incoming(pointer: _Pointer) -> str | None:
    if pointer.previous is None:
        return None
    delta = (
        pointer.position[0] - pointer.previous[0],
        pointer.position[1] - pointer.previous[1],
    )
    return _DIRECTION.get(delta)


def _neighbors(grid: tuple[str, ...], point: _Point, channel: _Channel) -> list[_Point]:
    here = _char(grid, point)
    alphabet = _SINGLE if channel == "execution" else _DOUBLE
    directions = _PORTS.get(here, "EWNS" if here in _NODES else "")
    neighbors = []
    for direction in directions:
        dx, dy = _STEP[direction]
        there = (point[0] + dx, point[1] + dy)
        other = _char(grid, there)
        wire = other in alphabet and _OPPOSITE[direction] in _PORTS[other]
        # A wire's end reaches a node; touching nodes are not connected.
        if wire or (other in _NODES and here not in _NODES):
            neighbors.append(there)
    return neighbors


def _exits(grid: tuple[str, ...], pointer: _Pointer, channel: _Channel) -> list[_Point]:
    return [
        point
        for point in _neighbors(grid, pointer.position, channel)
        if point != pointer.previous
    ]


def _directed_exit(
    grid: tuple[str, ...], pointer: _Pointer, direction: str, channel: _Channel
) -> list[_Point]:
    dx, dy = _STEP[direction]
    target = (pointer.position[0] + dx, pointer.position[1] + dy)
    return [target] if target in _neighbors(grid, pointer.position, channel) else []


def _router_direction(cell: str, pointer: _Pointer) -> str | None:
    incoming = _incoming(pointer)
    if pointer.channel == "data":
        if pointer.value is None:
            return incoming
        return (_WHITE_SIDE[cell], _BLACK_SIDE[cell])[pointer.value]
    if incoming is None:
        return None
    black = _BLACK_SIDE[cell]
    white = _WHITE_SIDE[cell]
    if _OPPOSITE[incoming] == white:
        return incoming
    if _OPPOSITE[incoming] == black:
        return black
    return {"N": "E", "E": "S", "S": "W", "W": "N"}[incoming]


def _at(cursor: int, axis: Literal["row", "column"], index: int) -> _Point:
    return (cursor, index) if axis == "column" else (index, cursor)


def _stack_axis(
    cells: Mapping[tuple[int, int], int],
    cursor: int,
    axis: Literal["row", "column"],
) -> list[_Point]:
    """Return the stack's occupied cells, beginning (at the axis) first."""
    along = 1 if axis == "column" else 0
    line = 0 if axis == "column" else 1
    return sorted((p for p in cells if p[line] == cursor), key=lambda p: p[along])


def _head(
    cells: Mapping[tuple[int, int], int],
    cursor: int,
    axis: Literal["row", "column"],
    value: int | None,
) -> tuple[dict[_Point, int], int | None]:
    """Push (``value``) or pop the head of the ``axis`` stack at ``cursor``."""
    working = dict(cells)
    along = 1 if axis == "column" else 0
    points = _stack_axis(cells, cursor, axis)
    if value is None:
        result = working.pop(_at(cursor, axis, 0), None)
        for point in points:
            if point[along]:
                working[_at(cursor, axis, point[along] - 1)] = working.pop(point)
        return working, result
    for point in reversed(points):
        working[_at(cursor, axis, point[along] + 1)] = working.pop(point)
    working[_at(cursor, axis, 0)] = value
    return working, None


def _tail(
    cells: Mapping[tuple[int, int], int],
    cursor: int,
    axis: Literal["row", "column"],
    value: int | None,
) -> tuple[dict[_Point, int], int | None]:
    """Push (``value``) or pop the tail of the ``axis`` stack at ``cursor``."""
    working = dict(cells)
    along = 1 if axis == "column" else 0
    points = _stack_axis(cells, cursor, axis)
    if value is None:
        return working, (working.pop(points[-1]) if points else None)
    working[_at(cursor, axis, points[-1][along] + 1 if points else 0)] = value
    return working, None


def _ordered_groups(
    grid: tuple[str, ...], pointers: tuple[_Pointer, ...]
) -> list[tuple[_Point, list[_Pointer]]]:
    groups: dict[_Point, list[_Pointer]] = defaultdict(list)
    for pointer in pointers:
        groups[pointer.position].append(pointer)
    return sorted(
        groups.items(),
        key=lambda item: (
            _PRIORITY.get(_char(grid, item[0]), 1),
            item[0][1],
            item[0][0],
        ),
    )


@dataclass
class _Step:
    """Mutable workspace for advancing one cycle's pointers."""

    grid: tuple[str, ...]
    cells: dict[_Point, int]
    cursor: int
    #: One entry per read the shell has answered: a codepoint, or ``None``
    #: for a read that hit EOF.  Every ``◇`` costs one entry, even past EOF,
    #: so the IO sees the same reads as the single-pass original.
    inputs: tuple[int | None, ...]
    draws: tuple[int, ...]
    set_ended: bool
    following: list[_Pointer] = field(default_factory=list)
    effects: list[int] = field(default_factory=list)
    halting: bool = False
    at: int = 0
    drawn: int = 0

    def _read_char(self) -> int | None:
        if self.at < len(self.inputs):
            value = self.inputs[self.at]
            self.at += 1
            return value
        raise _NeedInputError

    def _read_bit(self) -> int | None:
        """Return the current set's next bit, or ``None`` past its end."""
        char = None if self.set_ended else self._read_char()
        while char is not None and char != 10 and chr(char).isspace():
            char = self._read_char()
        if char == 10:
            self.set_ended = True
        if char is None or char == 10:
            return None
        if chr(char) not in "01":
            raise HaltError(
                "thisthat input must be a bit",
                hint="supply input bits as 0 or 1 characters, a set per line",
            )
        return int(chr(char))

    def _draw(self, upper: int) -> int:
        if self.drawn < len(self.draws):
            value = self.draws[self.drawn]
            self.drawn += 1
            return value % upper
        raise _NeedDrawError(upper)

    def _emit(
        self,
        pointer: _Pointer,
        exits: list[_Point],
        channel: _Channel,
        value: int | None = None,
    ) -> None:
        self.following.extend(
            _Pointer(exit_, pointer.position, channel, value) for exit_ in exits
        )

    def _pass(self, pointer: _Pointer) -> None:
        self._emit(
            pointer,
            _exits(self.grid, pointer, pointer.channel),
            pointer.channel,
            pointer.value,
        )

    def _send(self, pointer: _Pointer, value: int | None) -> None:
        """Send ``value`` down the data wires and go on down the execution ones."""
        self._emit(pointer, _exits(self.grid, pointer, "data"), "data", value)
        self._emit(pointer, _exits(self.grid, pointer, "execution"), "execution")

    def merge(self, cell: str, arrived: list[_Pointer]) -> None:
        """Fold the pointers that arrived together on ``cell`` into ``following``."""
        if cell == "◈":
            if len(arrived) < 2:
                self.following.extend(arrived)
                return
            for pointer in arrived:
                self._pass(pointer)
            return
        groups = (
            [p for p in arrived if p.channel == "execution"],
            [p for p in arrived if p.channel == "data"],
        )
        for pointers in groups:
            if not pointers:
                continue
            if cell in _GATE_VALUE and pointers[0].channel == "execution":
                value = _GATE_VALUE[cell]
                for pointer in pointers:
                    self._send(pointer, value)
                continue
            chosen = pointers[0]
            if cell == "◘" and len(pointers) > 1:
                chosen = pointers[self._draw(len(pointers))]
            if chosen.channel == "execution":
                value = None
            else:
                bits = [pointer.value for pointer in pointers]
                if cell == "◘":
                    value = int(not all(bit == 1 for bit in bits))
                elif cell == "□":
                    value = int(not any(bit == 1 for bit in bits))
                elif cell == "■":
                    value = int(any(bit == 1 for bit in bits))
                else:
                    value = sum(bit == 1 for bit in bits) % 2
            channel = chosen.channel
            self._emit(chosen, _exits(self.grid, chosen, channel), channel, value)

    def advance(self, pointer: _Pointer) -> None:
        """Advance one pointer through the cell it stands on."""
        cell = _char(self.grid, pointer.position)
        handler = self._CELL_HANDLERS.get(cell)
        if handler is None:
            raise HaltError(
                f"unsupported thisthat cell: {cell!r}",
                hint="use cells documented by esolangs describe --spec thisthat",
            )
        handler(self, pointer)

    def _cell_wire(self, pointer: _Pointer) -> None:
        """Carry a pointer along a single- or double-line wire."""
        cell = _char(self.grid, pointer.position)
        channel: _Channel = "execution" if cell in _SINGLE else "data"
        value = pointer.value if channel == "data" else None
        self._emit(pointer, _exits(self.grid, pointer, channel), channel, value)

    def _cell_start(self, pointer: _Pointer) -> None:
        """Send a start node's pointer down its execution wires."""
        self._emit(pointer, _exits(self.grid, pointer, "execution"), "execution")

    def _cell_halt(self, _pointer: _Pointer) -> None:
        """Halt at the end of this cycle."""
        self.halting = True

    def _cell_arrow(self, pointer: _Pointer) -> None:
        """Route a pointer through an arrow, never back the way it came."""
        cell = _char(self.grid, pointer.position)
        direction = _ARROW_DIRECTION[cell]
        incoming = _incoming(pointer)
        if cell in "△▷▽◁" and incoming not in (
            None,
            direction,
            _OPPOSITE[direction],
        ):
            direction = incoming
        exits = [
            point
            for point in _directed_exit(self.grid, pointer, direction, pointer.channel)
            if point != pointer.previous
        ]
        self._emit(pointer, exits, pointer.channel, pointer.value)

    def _cell_pause(self, pointer: _Pointer) -> None:
        """Hold a pointer for one cycle, then let it through."""
        if pointer.paused:
            self._pass(pointer)
        else:
            self.following.append(
                _Pointer(
                    pointer.position,
                    pointer.previous,
                    pointer.channel,
                    pointer.value,
                    paused=True,
                )
            )

    def _cell_input(self, pointer: _Pointer) -> None:
        """Read a bit on execution entry; print one on data entry."""
        if pointer.channel == "execution":
            self._send(pointer, self._read_bit())
        elif pointer.value is not None:
            self.effects.append(pointer.value)
        elif self.set_ended:
            self.set_ended = False
        else:
            while self._read_char() not in (None, 10):
                pass

    def _cell_stack(self, pointer: _Pointer) -> None:
        """Push to or pop from the head or tail of the selected bistack axis."""
        cell = _char(self.grid, pointer.position)
        axis: Literal["row", "column"] = "column" if cell in "⬓⬒" else "row"
        operation = _tail if cell in "◨⬒" else _head
        if pointer.channel == "execution":
            self.cells, value = operation(self.cells, self.cursor, axis, None)
            self._send(pointer, value)
        else:
            if pointer.value is not None:
                self.cells, _ = operation(self.cells, self.cursor, axis, pointer.value)
            self._emit(pointer, _exits(self.grid, pointer, "execution"), "execution")

    def _cell_cursor(self, pointer: _Pointer) -> None:
        """Move the bistack cursor up (``◹``) or down (``◺``)."""
        cell = _char(self.grid, pointer.position)
        if pointer.channel == "data" and pointer.value != 1:
            return
        moved = cell == "◹" or self.cursor > 0
        if moved:
            self.cursor += 1 if cell == "◹" else -1
        if pointer.channel == "execution":
            self._send(pointer, int(moved))
        else:
            self._emit(pointer, _exits(self.grid, pointer, "execution"), "execution")

    def _cell_router(self, pointer: _Pointer) -> None:
        """Route an execution pointer through a black/white half-cell."""
        cell = _char(self.grid, pointer.position)
        route_direction = _router_direction(cell, pointer)
        exits = (
            []
            if route_direction is None
            else _directed_exit(self.grid, pointer, route_direction, "execution")
        )
        self._emit(pointer, exits, "execution")

    def _cell_constant(self, pointer: _Pointer) -> None:
        """Send the gate's constant down the data wires."""
        cell = _char(self.grid, pointer.position)
        self._send(pointer, _GATE_VALUE[cell])

    _CELL_HANDLERS: ClassVar[dict[str, Callable[[_Step, _Pointer], None]]] = {
        **dict.fromkeys(_SINGLE | _DOUBLE, _cell_wire),
        "▣": _cell_start,
        "◉": _cell_halt,
        **dict.fromkeys(_ARROWS, _cell_arrow),
        "◯": _pass,
        "◔": _cell_pause,
        "◇": _cell_input,
        **dict.fromkeys("◧⬓◨⬒", _cell_stack),
        **dict.fromkeys("◹◺", _cell_cursor),
        **dict.fromkeys(_BLACK_SIDE, _cell_router),
        **dict.fromkeys(_GATE_VALUE, _cell_constant),
    }


# :func:`_advance` is a pure transition over an immutable :data:`_Core`.  It consumes
# input characters and ``◘`` draws from explicit tuples and returns the requested print
# effects; it never touches the ports.  When it runs out of an explicit input or draw
# it raises :class:`_NeedInputError`/:class:`_NeedDrawError`, and :meth:`_Machine.step`
# -- the shell -- supplies one more from the port or the draw source and retries.  A
# retry is sound because the transition is pure.
def _advance(
    core: _Core,
    grid: tuple[str, ...],
    inputs: tuple[int | None, ...] = (),
    draws: tuple[int, ...] = (),
) -> tuple[_Core, tuple[int, ...]]:
    """Return the next core and the numbers a ``◇`` printed this cycle.

    Pure.  ``inputs``/``draws`` are the values the shell has supplied so
    far; running short raises :class:`_NeedInputError`/``_NeedDrawError``
    carrying the prints collected so far, so the shell can flush them and
    add one value.  Any other fault is wrapped in :class:`_FaultError` with the
    same prefix.
    """
    pointers, cells, cursor, halted, set_ended = core
    if halted:
        return core, ()
    step = _Step(
        grid=grid,
        cells=dict(cells),
        cursor=cursor,
        inputs=inputs,
        draws=draws,
        set_ended=set_ended,
    )
    try:
        for position, arrived in _ordered_groups(grid, pointers):
            cell = _char(grid, position)
            is_data_gate = cell in _GATE_VALUE and any(
                p.channel == "data" for p in arrived
            )
            if cell in "◘◈" or is_data_gate:
                step.merge(cell, arrived)
            else:
                for pointer in arrived:
                    step.advance(pointer)
    except (_NeedInputError, _NeedDrawError) as need:
        need.effects = tuple(step.effects)
        raise
    except Exception as error:
        raise _FaultError(error, tuple(step.effects)) from error
    following = () if step.halting else tuple(step.following)
    return (
        (
            following,
            MappingProxyType(step.cells),
            step.cursor,
            step.halting,
            step.set_ended,
        ),
        tuple(step.effects),
    )


class _Machine:
    """thisthat shell: one immutable :data:`_Core`, rebound per cycle."""

    ip_shape = "grid"

    def __init__(
        self, code: list[str], io: IO | None = None, rng: Randomness | None = None
    ) -> None:
        self.io = io if io is not None else IO()
        self.rng = rng
        width = max(map(len, code), default=0)
        self.grid = tuple(line.ljust(width) for line in code)
        starts = tuple(
            _Pointer((x, y), None)
            for y, line in enumerate(self.grid)
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
            for line in self.grid
            for cell in line
            if cell != " " and cell not in _PORTS and cell not in _NODES
        }
        if unknown:
            raise HaltError(
                f"unsupported thisthat cell: {min(unknown)!r}",
                hint="use cells documented by esolangs describe --spec thisthat",
            )
        self.state: _Core = (starts, MappingProxyType({}), 0, False, False)
        self._input_reads = 0

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

    def snapshot(self) -> _State:
        pointers, cells, cursor, halted, set_ended = self.state
        return (
            pointers,
            tuple(sorted(cells.items())),
            cursor,
            halted,
            self.io.progress(),
            self._input_reads,
            self.grid,
            set_ended,
        )

    def branching_snapshot(self) -> _State:
        """Return immutable state for exhaustive random-merge search."""
        return self.snapshot()

    def branching_halted(self, state: object) -> bool:
        """Report whether a branch halted or lost every pointer."""
        if not isinstance(state, tuple) or len(state) != 8:
            return False
        return bool(state[3]) or not state[0]

    def branching_successors(
        self, state: object, limit: int
    ) -> tuple[_State, ...] | None:
        """Return every random-merge successor, or ``None`` before input or a flag."""
        if not isinstance(state, tuple) or len(state) != 8:
            raise TypeError("invalid thisthat branch state")
        current: _State = state
        if self.branching_halted(current):
            return (current,)
        pointers, cells, cursor, halted, progress, reads, grid, set_ended = current
        if grid != self.grid:
            raise ValueError("branch belongs to another thisthat program")
        if any(
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
        branch_count = 1
        for radix in radices:
            branch_count *= radix
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
        choices = product(*(range(radix) for radix in radices)) if radices else [()]
        successors = []
        for branch_choices in choices:
            new_core, _effects = _advance(core, grid, draws=tuple(branch_choices))
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

    def _merge(
        self, cell: str, arrived: list[_Pointer], following: list[_Pointer]
    ) -> None:
        saved = list(following)
        draws: tuple[int, ...] = ()
        while True:
            following[:] = saved
            step = self._workspace(following)
            step.draws = draws
            try:
                step.merge(cell, arrived)
                return
            except _NeedDrawError as need:
                draws = (*draws, draw(self.rng, need.upper))

    def _advance_one(self, pointer: _Pointer, following: list[_Pointer]) -> None:
        saved = list(following)
        draws: tuple[int, ...] = ()
        while True:
            following[:] = saved
            step = self._workspace(following)
            step.draws = draws
            try:
                step.advance(pointer)
                return
            except _NeedDrawError as need:
                draws = (*draws, draw(self.rng, need.upper))

    def _flush(self, effects: tuple[int, ...], flushed: int) -> None:
        """Write the prints beyond ``flushed``; a prefix is written once."""
        for value in effects[flushed:]:
            self.io.print_num(value)

    def step(self) -> None:
        """Execute one cycle, reading, drawing and writing as the shell.

        Each request or fault carries the prints collected before it; this
        flushes that prefix exactly once before asking for another value or
        re-raising the fault, so output order and partial output match the
        single-pass original.
        """
        if self.halted:
            return
        inputs: tuple[int | None, ...] = ()
        draws: tuple[int, ...] = ()
        flushed = 0
        while True:
            try:
                core, effects = _advance(self.state, self.grid, inputs, draws=draws)
            except _NeedInputError as need:
                self._flush(need.effects, flushed)
                flushed = len(need.effects)
                # One IO attempt per ``◇`` read, EOF included, so the port
                # sees exactly the reads the single-pass original made.
                try:
                    inputs = (*inputs, self.io.input_char())
                    self._input_reads += 1
                except EOFError:
                    inputs = (*inputs, None)
            except _NeedDrawError as need:
                self._flush(need.effects, flushed)
                flushed = len(need.effects)
                draws = (*draws, draw(self.rng, need.upper))
            except _FaultError as fault:
                self._flush(fault.effects, flushed)
                raise fault.cause from None
            else:
                self.state = core
                self._flush(effects, flushed)
                return


def run(code: list[str], io: IO, rng: Randomness | None = None) -> None:
    """Run a thisthat program until it halts or has no pointers left."""
    machine = _Machine(code, io, rng)
    drive(machine)


if __name__ == "__main__":
    script_main(run, shape="keep")
