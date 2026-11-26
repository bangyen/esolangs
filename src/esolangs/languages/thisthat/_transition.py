"""Advance ThisThat pointers and shared bistacks through one tick."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import ClassVar, Literal

from esolangs.exceptions import HaltError
from esolangs.languages.thisthat._topology import (
    _ARROW_DIRECTION,
    _ARROWS,
    _BLACK_SIDE,
    _DOUBLE,
    _OPPOSITE,
    _SINGLE,
    _Channel,
    _char,
    _directed_exit,
    _exits,
    _incoming,
    _Point,
    _router_direction,
)

#: Each constant gate's value; ``▦`` sends nothing.
_GATE_VALUE: dict[str, int | None] = {"□": 0, "■": 1, "▦": None}

_PRIORITY = {"◘": 2, "◈": 2, "◹": 2, "◺": 2, "◇": 3, "◧": 3, "⬓": 3, "◨": 3, "⬒": 3}


@dataclass(frozen=True)
class _Pointer:
    position: _Point
    previous: _Point | None
    channel: _Channel = "execution"
    value: int | None = None
    paused: bool = False


# Snapshot wire records use the registered interpreter module.
_Pointer.__module__ = "esolangs.languages.thisthat.interpreter"

type _Cells = Mapping[tuple[int, int], int]
type _Core = tuple[tuple[_Pointer, ...], _Cells, int, bool, bool]


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
