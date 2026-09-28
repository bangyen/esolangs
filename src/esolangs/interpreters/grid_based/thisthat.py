"""Interpreter for the deterministic thisthat core used by its generator.

Single-line wires carry execution pointers; double-line wires carry bits.
This implements starts, halts, bit I/O, bistack head-pop and tail-push,
horizontal and vertical bit routers, and constant-bit nodes.  The random merge,
barrier, arrow, and stack-cursor nodes abort with :class:`HaltError` rather than
guessing at concurrent semantics.  Input is one ``0`` or ``1`` per line; EOF
propagates from :class:`~esolangs.interpreters.io.IO`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

_STEP = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}
_OPPOSITE = {"E": "W", "W": "E", "N": "S", "S": "N"}
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
_SINGLE = set("─│┌┐└┘├┤┬┴┼")
_DOUBLE = set("═║╔╗╚╝╠╣╦╩╬")
_NODES = set("▣◇◨◧◑◒□■◉")


@dataclass(frozen=True)
class _Pointer:
    position: tuple[int, int]
    previous: tuple[int, int] | None
    data: int | None = None


type _State = tuple[tuple[_Pointer, ...], tuple[int, ...], bool]


class _Machine:
    """A cycle-synchronous thisthat machine for the deterministic core."""

    ip_shape = "grid"

    def __init__(self, code: list[str], io: IO | None = None) -> None:
        self.io = io if io is not None else IO()
        self.width = max(map(len, code), default=0)
        self.grid = tuple(line.ljust(self.width) for line in code)
        starts = [
            (x, y)
            for y, line in enumerate(self.grid)
            for x, cell in enumerate(line)
            if cell == "▣"
        ]
        if len(starts) != 1:
            raise HaltError("thisthat needs exactly one start node")
        self.pointers: tuple[_Pointer, ...] = (_Pointer(starts[0], None),)
        self.bistack: tuple[int, ...] = ()
        self._halted = False

    def _char(self, point: tuple[int, int]) -> str:
        x, y = point
        if 0 <= y < len(self.grid) and 0 <= x < self.width:
            return self.grid[y][x]
        return " "

    def _neighbors(
        self, point: tuple[int, int], kind: set[str]
    ) -> list[tuple[int, int]]:
        here = self._char(point)
        directions = _PORTS.get(here, "EWNS" if here in _NODES else "")
        neighbors = []
        for direction in directions:
            dx, dy = _STEP[direction]
            there = (point[0] + dx, point[1] + dy)
            other = self._char(there)
            if other in kind and _OPPOSITE[direction] in _PORTS[other]:
                neighbors.append(there)
            elif other in _NODES:
                neighbors.append(there)
        return neighbors

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
        return []

    @property
    def stack(self) -> list[object]:
        return list(self.bistack)

    def snapshot(self) -> tuple[object, ...]:
        return (self.pointers, self.bistack, self.io.position())

    def step(self) -> None:
        if self.halted:
            return
        following: list[_Pointer] = []
        stack = list(self.bistack)
        groups: dict[tuple[int, int], list[_Pointer]] = defaultdict(list)
        for pointer in self.pointers:
            groups[pointer.position].append(pointer)
        for position, arrived in groups.items():
            if len(arrived) != 1:
                raise HaltError("unsupported thisthat pointer merge")
            pointer = arrived[0]
            cell = self._char(position)
            if cell in _SINGLE | _DOUBLE:
                kind = _DOUBLE if cell in _DOUBLE else _SINGLE
                data = pointer.data if kind is _DOUBLE else None
                exits = [
                    p for p in self._neighbors(position, kind) if p != pointer.previous
                ]
            elif cell == "▣":
                data, exits = None, self._neighbors(position, _SINGLE)
            elif cell == "◇" and pointer.data is None:
                bit = self.io.input_str()
                if bit not in {"0", "1"}:
                    raise HaltError("thisthat input must be a bit")
                data, exits = int(bit), self._neighbors(position, _DOUBLE)
            elif cell == "◇":
                data_value = pointer.data
                if data_value is None:
                    raise HaltError("thisthat output needs data")
                self.io.print_num(data_value)
                data, exits = data_value, []
            elif cell == "◨":
                if pointer.data is None:
                    raise HaltError("thisthat tail push needs data")
                stack.append(pointer.data)
                data, exits = None, self._neighbors(position, _SINGLE)
            elif cell == "◧":
                if not stack:
                    raise HaltError("thisthat head pop from empty bistack")
                data, exits = stack.pop(0), self._neighbors(position, _DOUBLE)
            elif cell in "◑◒":
                if pointer.data is None:
                    raise HaltError("thisthat router needs data")
                direction = (
                    ("W", "E")[pointer.data]
                    if cell == "◑"
                    else ("N", "S")[pointer.data]
                )
                dx, dy = _STEP[direction]
                target = (position[0] + dx, position[1] + dy)
                if target not in self._neighbors(position, _SINGLE):
                    raise HaltError("thisthat router has no selected exit")
                data, exits = None, [target]
            elif cell in "□■":
                data, exits = int(cell == "■"), self._neighbors(position, _DOUBLE)
            elif cell == "◉":
                self._halted = True
                return
            else:
                raise HaltError(f"unsupported thisthat cell: {cell!r}")
            following.extend(_Pointer(exit_, position, data) for exit_ in exits)
        self.bistack = tuple(stack)
        self.pointers = tuple(following)


def run(code: list[str], io: IO) -> None:
    """Run the deterministic thisthat instruction subset."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    script_main(run, shape="keep")
