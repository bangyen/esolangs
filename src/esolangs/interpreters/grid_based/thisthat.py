"""Interpreter for thisthat.

Single-line wires carry execution pointers; double-line wires carry a zero,
one, or empty transfer. Every pointer advances once per cycle, ordered by node
priority and grid position. Coincident pointers implement merges, logic, and
barriers; the shared bistack is a sparse plane whose cursor moves diagonally.

The specification says a cursor move can fail without defining the collision;
this interpreter refuses a move exactly when its destination cell holds a bit.

EOF makes ``◇`` send an empty transfer; printing an empty transfer produces no
text. Malformed input, connections, or source
raise :class:`~esolangs.exceptions.HaltError`. ``◘`` uses the shared randomness
hook, so callers may inject a reproducible source.

External bits are consecutive 0 or 1 characters, ignoring whitespace; the spec
does not define stdin framing.
"""

from __future__ import annotations

import copy
from collections import defaultdict
from dataclasses import dataclass
from itertools import product
from typing import Literal

from esolangs._drive import drive
from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import Randomness, draw

type _Point = tuple[int, int]
type _Channel = Literal["execution", "data"]

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
_ARROW_DIRECTION = dict(zip("▶◀▲▼▷◁△▽", "EWNS EWNS".replace(" ", ""), strict=True))
_BLACK_SIDE = {"◐": "W", "◑": "E", "◒": "S", "◓": "N"}
_WHITE_SIDE = {node: _OPPOSITE[side] for node, side in _BLACK_SIDE.items()}


@dataclass(frozen=True)
class _Pointer:
    position: _Point
    previous: _Point | None
    channel: _Channel = "execution"
    value: int | None = None
    paused: bool = False


type _State = tuple[
    tuple[_Pointer, ...], tuple[tuple[_Point, int], ...], _Point, bool, int
]


class _BranchDraw:
    """A finite sequence of merge choices for one exhaustive branch."""

    def __init__(self, choices: tuple[int, ...]) -> None:
        self.choices = iter(choices)

    def randbelow(self, upper: int) -> int:
        """Return the next enumerated choice."""
        return next(self.choices) % upper


class _Machine:
    """A cycle-synchronous thisthat machine with a shared planar bistack."""

    ip_shape = "grid"

    def __init__(
        self, code: list[str], io: IO | None = None, rng: Randomness | None = None
    ) -> None:
        self.io = io if io is not None else IO()
        self.rng = rng
        self.width = max(map(len, code), default=0)
        self.grid = tuple(line.ljust(self.width) for line in code)
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
        self.pointers: tuple[_Pointer, ...] = starts
        self.cells: dict[_Point, int] = {}
        self.cursor: _Point = (0, 0)
        self._halted = False

    def _char(self, point: _Point) -> str:
        x, y = point
        if 0 <= y < len(self.grid) and 0 <= x < self.width:
            return self.grid[y][x]
        return " "

    def _neighbors(self, point: _Point, channel: _Channel) -> list[_Point]:
        here = self._char(point)
        alphabet = _SINGLE if channel == "execution" else _DOUBLE
        directions = _PORTS.get(here, "EWNS" if here in _NODES else "")
        neighbors = []
        for direction in directions:
            dx, dy = _STEP[direction]
            there = (point[0] + dx, point[1] + dy)
            other = self._char(there)
            connected_wire = other in alphabet and _OPPOSITE[direction] in _PORTS[other]
            if connected_wire or other in _NODES:
                neighbors.append(there)
        return neighbors

    def _exits(self, pointer: _Pointer, channel: _Channel) -> list[_Point]:
        return [
            point
            for point in self._neighbors(pointer.position, channel)
            if point != pointer.previous
        ]

    def _directed_exit(
        self, pointer: _Pointer, direction: str, channel: _Channel
    ) -> list[_Point]:
        dx, dy = _STEP[direction]
        target = (pointer.position[0] + dx, pointer.position[1] + dy)
        return [target] if target in self._neighbors(pointer.position, channel) else []

    def _emit(
        self,
        following: list[_Pointer],
        pointer: _Pointer,
        exits: list[_Point],
        channel: _Channel,
        value: int | None = None,
    ) -> None:
        following.extend(
            _Pointer(exit_, pointer.position, channel, value) for exit_ in exits
        )

    def _stack_axis(self, axis: Literal["row", "column"]) -> list[_Point]:
        x, y = self.cursor
        if axis == "column":
            return sorted(
                (p for p in self.cells if p[0] == x and p[1] > y), key=lambda p: p[1]
            )
        return sorted(
            (p for p in self.cells if p[1] == y and p[0] < x), key=lambda p: -p[0]
        )

    def _head(self, axis: Literal["row", "column"], value: int | None) -> int | None:
        x, y = self.cursor
        vertical = axis == "column"
        points = self._stack_axis(axis)
        if value is None:
            result = self.cells.pop(points[0], None) if points else None
            for point in points[1:]:
                bit = self.cells.pop(point)
                shifted = (
                    (point[0], point[1] - 1) if vertical else (point[0] + 1, point[1])
                )
                self.cells[shifted] = bit
            return result
        for point in reversed(points):
            bit = self.cells.pop(point)
            shifted = (point[0], point[1] + 1) if vertical else (point[0] - 1, point[1])
            self.cells[shifted] = bit
        self.cells[(x, y + 1) if vertical else (x - 1, y)] = value
        return None

    def _tail(self, axis: Literal["row", "column"], value: int | None) -> int | None:
        x, y = self.cursor
        vertical = axis == "column"
        points = self._stack_axis(axis)
        if value is None:
            return self.cells.pop(points[-1], None) if points else None
        if points:
            tail = points[-1]
            point = (tail[0], tail[1] + 1) if vertical else (tail[0] - 1, tail[1])
        else:
            point = (x, y + 1) if vertical else (x - 1, y)
        self.cells[point] = value
        return None

    @property
    def halted(self) -> bool:
        return self._halted or not self.pointers

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

    def snapshot(self) -> tuple[object, ...]:
        return (
            self.pointers,
            tuple(sorted(self.cells.items())),
            self.cursor,
            self._halted,
            self.io.position(),
        )

    def branching_snapshot(self) -> _State:
        """Return immutable state for exhaustive random-merge search."""
        return (
            self.pointers,
            tuple(sorted(self.cells.items())),
            self.cursor,
            self._halted,
            self.io.position(),
        )

    def branching_halted(self, state: object) -> bool:
        """Report whether a branch halted or lost every pointer."""
        if not isinstance(state, tuple) or len(state) != 5:
            return False
        return bool(state[3]) or not state[0]

    def _restore(self, state: _State) -> None:
        self.pointers = state[0]
        self.cells = dict(state[1])
        self.cursor = state[2]
        self._halted = state[3]

    def branching_successors(
        self, state: object, limit: int
    ) -> tuple[_State, ...] | None:
        """Return every random-merge successor, or ``None`` before input."""
        if not isinstance(state, tuple) or len(state) != 5:
            raise TypeError("invalid thisthat branch state")
        current: _State = state
        if self.branching_halted(current):
            return (current,)
        pointers = current[0]
        if any(
            self._char(pointer.position) == "◇" and pointer.channel == "execution"
            for pointer in pointers
        ):
            return None
        groups: dict[_Point, list[_Pointer]] = defaultdict(list)
        for pointer in pointers:
            groups[pointer.position].append(pointer)
        radices: list[int] = []
        for position, arrived in groups.items():
            if self._char(position) != "◘":
                continue
            for channel in ("execution", "data"):
                count = sum(pointer.channel == channel for pointer in arrived)
                if count > 1:
                    radices.append(count)
        branch_count = 1
        for radix in radices:
            branch_count *= radix
        if branch_count > limit:
            raise TimeoutError(
                f"undecided after {limit} random merges in one thisthat cycle"
            )
        choices = product(*(range(radix) for radix in radices)) if radices else [()]
        successors = []
        for branch_choices in choices:
            branch = copy.deepcopy(self)
            branch._restore(current)  # noqa: SLF001 - same-class state fork
            branch.rng = _BranchDraw(tuple(branch_choices))
            branch.step()
            successors.append(branch.branching_snapshot())
        return tuple(successors)

    def _incoming(self, pointer: _Pointer) -> str | None:
        if pointer.previous is None:
            return None
        delta = (
            pointer.position[0] - pointer.previous[0],
            pointer.position[1] - pointer.previous[1],
        )
        return _DIRECTION.get(delta)

    def _router_direction(self, cell: str, pointer: _Pointer) -> str | None:
        incoming = self._incoming(pointer)
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

    def _merge(
        self, cell: str, arrived: list[_Pointer], following: list[_Pointer]
    ) -> None:
        if cell == "◈":
            if len(arrived) < 2:
                following.extend(arrived)
                return
            for pointer in arrived:
                self._emit(
                    following,
                    pointer,
                    self._exits(pointer, pointer.channel),
                    pointer.channel,
                    pointer.value,
                )
            return
        groups = (
            [p for p in arrived if p.channel == "execution"],
            [p for p in arrived if p.channel == "data"],
        )
        for pointers in groups:
            if not pointers:
                continue
            if cell in "□■▦" and pointers[0].channel == "execution":
                value = {"□": 0, "■": 1, "▦": None}[cell]
                for pointer in pointers:
                    self._emit(
                        following,
                        pointer,
                        self._exits(pointer, "data"),
                        "data",
                        value,
                    )
                continue
            chosen = pointers[0]
            if cell == "◘" and len(pointers) > 1:
                chosen = pointers[draw(self.rng, len(pointers))]
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
            channel: _Channel = "execution" if chosen.channel == "execution" else "data"
            self._emit(following, chosen, self._exits(chosen, channel), channel, value)

    def _advance_one(self, pointer: _Pointer, following: list[_Pointer]) -> None:
        cell = self._char(pointer.position)
        if cell in _SINGLE | _DOUBLE:
            channel: _Channel = "execution" if cell in _SINGLE else "data"
            value = pointer.value if channel == "data" else None
            self._emit(
                following, pointer, self._exits(pointer, channel), channel, value
            )
        elif cell == "▣":
            self._emit(
                following, pointer, self._exits(pointer, "execution"), "execution"
            )
        elif cell == "◉":
            self._halted = True
        elif cell in _ARROWS:
            direction = _ARROW_DIRECTION[cell]
            incoming = self._incoming(pointer)
            white = cell in "△▷▽◁"
            if (
                not white
                or incoming is None
                or incoming == direction
                or incoming == _OPPOSITE[direction]
            ):
                exits = self._directed_exit(pointer, direction, pointer.channel)
                self._emit(following, pointer, exits, pointer.channel, pointer.value)
        elif cell == "◯":
            self._emit(
                following,
                pointer,
                self._exits(pointer, pointer.channel),
                pointer.channel,
                pointer.value,
            )
        elif cell == "◔":
            if pointer.paused:
                self._emit(
                    following,
                    pointer,
                    self._exits(pointer, pointer.channel),
                    pointer.channel,
                    pointer.value,
                )
            else:
                following.append(
                    _Pointer(
                        pointer.position,
                        pointer.previous,
                        pointer.channel,
                        pointer.value,
                        paused=True,
                    )
                )
        elif cell == "◇":
            if pointer.channel == "execution":
                try:
                    bit = self.io.input_bit()
                except EOFError:
                    value = None
                except ValueError:
                    raise HaltError(
                        "thisthat input must be a bit",
                        hint="supply input bits as 0 or 1 characters",
                    ) from None
                else:
                    value = bit
                self._emit(
                    following, pointer, self._exits(pointer, "data"), "data", value
                )
            elif pointer.value is not None:
                self.io.print_num(pointer.value)
        elif cell in "◧⬓◨⬒":
            axis: Literal["row", "column"] = "column" if cell in "⬓⬒" else "row"
            operation = self._tail if cell in "◨⬒" else self._head
            if pointer.channel == "execution":
                value = operation(axis, None)
                self._emit(
                    following, pointer, self._exits(pointer, "data"), "data", value
                )
            else:
                if pointer.value is not None:
                    operation(axis, pointer.value)
                self._emit(
                    following, pointer, self._exits(pointer, "execution"), "execution"
                )
        elif cell in "◹◺":
            if pointer.channel == "data" and pointer.value != 1:
                return
            delta = -1 if cell == "◹" else 1
            target = (self.cursor[0] + delta, self.cursor[1] + delta)
            moved = target not in self.cells
            if moved:
                self.cursor = target
            if pointer.channel == "execution":
                self._emit(
                    following, pointer, self._exits(pointer, "data"), "data", int(moved)
                )
            else:
                self._emit(
                    following, pointer, self._exits(pointer, "execution"), "execution"
                )
        elif cell in _BLACK_SIDE:
            route_direction = self._router_direction(cell, pointer)
            exits = (
                []
                if route_direction is None
                else self._directed_exit(pointer, route_direction, "execution")
            )
            self._emit(following, pointer, exits, "execution")
        elif cell in "□■▦":
            value = {"□": 0, "■": 1, "▦": None}[cell]
            self._emit(following, pointer, self._exits(pointer, "data"), "data", value)
        else:
            raise HaltError(
                f"unsupported thisthat cell: {cell!r}",
                hint="use cells documented by esolangs describe --spec thisthat",
            )

    def step(self) -> None:
        if self.halted:
            return
        groups: dict[_Point, list[_Pointer]] = defaultdict(list)
        for pointer in self.pointers:
            groups[pointer.position].append(pointer)
        following: list[_Pointer] = []
        ordered = sorted(
            groups.items(),
            key=lambda item: (
                _PRIORITY.get(self._char(item[0]), 1),
                item[0][1],
                item[0][0],
            ),
        )
        for position, arrived in ordered:
            cell = self._char(position)
            is_data_gate = cell in "□■▦" and any(p.channel == "data" for p in arrived)
            if cell in "◘◈" or is_data_gate:
                self._merge(cell, arrived, following)
            else:
                for pointer in arrived:
                    self._advance_one(pointer, following)
            if self._halted:
                following.clear()
                break
        self.pointers = tuple(following)


def run(code: list[str], io: IO, rng: Randomness | None = None) -> None:
    """Run a thisthat program until it halts or has no pointers left."""
    machine = _Machine(code, io, rng)
    drive(machine)


if __name__ == "__main__":
    script_main(run, shape="keep")
