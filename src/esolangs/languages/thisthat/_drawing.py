"""Draw thisthat nodes, wires, and the input loader."""

from itertools import pairwise
from typing import Literal

_STEP = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}
_OPPOSITE = {"E": "W", "W": "E", "N": "S", "S": "N"}
_PORTS = [
    frozenset(ports)
    for ports in (
        "EW",
        "NS",
        "ES",
        "WS",
        "EN",
        "WN",
        "ENS",
        "WNS",
        "EWS",
        "EWN",
        "EWNS",
    )
]
_SINGLE = dict(zip(_PORTS, "─│┌┐└┘├┤┬┴┼", strict=True))
_DOUBLE = dict(zip(_PORTS, "═║╔╗╚╝╠╣╦╩╬", strict=True))
_NAME = {step: name for name, step in _STEP.items()}


def _path(
    start: tuple[int, int],
    end: tuple[int, int],
    first_axis: Literal["horizontal", "vertical"],
) -> list[tuple[int, int]]:
    x, y = start
    points = [(x, y)]
    axes: tuple[tuple[int, int], ...] = ((0, end[0]), (1, end[1]))
    if first_axis == "vertical":
        axes = tuple(reversed(axes))
    for axis, target in axes:
        while (x, y)[axis] != target:
            if axis == 0:
                x += 1 if target > x else -1
            else:
                y += 1 if target > y else -1
            points.append((x, y))
    return points


def _first_axis(horizontal: int) -> Literal["horizontal", "vertical"]:
    return "horizontal" if horizontal else "vertical"


class _Builder:
    def __init__(self) -> None:
        self.nodes: dict[tuple[int, int], str] = {}
        self.wires: dict[tuple[int, int], tuple[str, set[str]]] = {}

    def node(self, point: tuple[int, int], glyph: str) -> None:
        if point in self.nodes:
            raise ValueError("thisthat layout collision")
        self.wires.pop(point, None)
        self.nodes[point] = glyph

    def connect(self, points: list[tuple[int, int]], kind: str) -> None:
        for left, right in pairwise(points):
            delta = (right[0] - left[0], right[1] - left[1])
            direction = _NAME[delta]
            for point, port in ((left, direction), (right, _OPPOSITE[direction])):
                if point in self.nodes:
                    continue
                old_kind, ports = self.wires.setdefault(point, (kind, set()))
                if old_kind != kind:
                    raise ValueError("thisthat wire collision")
                ports.add(port)

    def cells(self) -> set[tuple[int, int]]:
        return set(self.nodes) | set(self.wires)

    def render(self) -> str:
        cells = self.cells()
        min_x = min(x for x, _ in cells)
        min_y = min(y for _, y in cells)
        width = max(x for x, _ in cells) - min_x + 1
        height = max(y for _, y in cells) - min_y + 1
        rows = [[" "] * width for _ in range(height)]
        for (x, y), glyph in self.nodes.items():
            rows[y - min_y][x - min_x] = glyph
        for (x, y), (kind, ports) in self.wires.items():
            glyphs = _SINGLE if kind == "single" else _DOUBLE
            rows[y - min_y][x - min_x] = glyphs[frozenset(ports)]
        return "\n".join("".join(row).rstrip() for row in rows)


def _draw_loader(
    builder: _Builder,
    start: tuple[int, int],
    n: int,
    essential: list[int],
) -> tuple[int, int]:
    """Draw the start node and one read per input, rightward; return the end.

    An essential input's read is followed by its tail push (◨); an ignored
    input's read sends its bit nowhere and goes straight on.
    """
    builder.node(start, "▣")
    previous = start
    for i in range(n):
        diamond = (previous[0] + 2, start[1])
        builder.node(diamond, "◇")
        builder.connect(_path(previous, diamond, "horizontal"), "single")
        previous = diamond
        if i in essential:
            pushed = (diamond[0] + 2, start[1])
            builder.node(pushed, "◨")
            builder.connect(_path(diamond, pushed, "horizontal"), "double")
            previous = pushed
    return previous
