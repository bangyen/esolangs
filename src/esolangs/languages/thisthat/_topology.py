"""Resolve wire connections and exits on a thisthat grid."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from esolangs.languages.thisthat._transition import _Pointer


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
_ARROW_DIRECTION = dict(zip("▶◀▲▼▷◁△▽", "EWNSEWNS", strict=True))
_BLACK_SIDE = {"◐": "W", "◑": "E", "◒": "S", "◓": "N"}
_WHITE_SIDE = {node: _OPPOSITE[side] for node, side in _BLACK_SIDE.items()}


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
