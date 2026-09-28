"""thisthat boolean generator: a bistack-routed planar decision tree."""

from esolangs.tools.helpers import _validate_truth_table

_STEP = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}
_OPPOSITE = {"E": "W", "W": "E", "N": "S", "S": "N"}
_SINGLE = {
    frozenset("EW"): "─",
    frozenset("NS"): "│",
    frozenset("ES"): "┌",
    frozenset("WS"): "┐",
    frozenset("EN"): "└",
    frozenset("WN"): "┘",
    frozenset("ENS"): "├",
    frozenset("WNS"): "┤",
    frozenset("EWS"): "┬",
    frozenset("EWN"): "┴",
    frozenset("EWNS"): "┼",
}
_DOUBLE = {
    frozenset("EW"): "═",
    frozenset("NS"): "║",
    frozenset("ES"): "╔",
    frozenset("WS"): "╗",
    frozenset("EN"): "╚",
    frozenset("WN"): "╝",
    frozenset("ENS"): "╠",
    frozenset("WNS"): "╣",
    frozenset("EWS"): "╦",
    frozenset("EWN"): "╩",
    frozenset("EWNS"): "╬",
}


def _path(
    start: tuple[int, int], end: tuple[int, int], horizontal_first: bool
) -> list[tuple[int, int]]:
    x, y = start
    points = [(x, y)]
    axes = (
        ((0, end[0]), (1, end[1])) if horizontal_first else ((1, end[1]), (0, end[0]))
    )
    for axis, target in axes:
        while (x, y)[axis] != target:
            if axis == 0:
                x += 1 if target > x else -1
            else:
                y += 1 if target > y else -1
            points.append((x, y))
    return points


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
        for left, right in zip(points, points[1:]):
            delta = (right[0] - left[0], right[1] - left[1])
            direction = next(name for name, step in _STEP.items() if step == delta)
            for point, port in ((left, direction), (right, _OPPOSITE[direction])):
                if point in self.nodes:
                    continue
                old_kind, ports = self.wires.setdefault(point, (kind, set()))
                if old_kind != kind:
                    raise ValueError("thisthat wire collision")
                ports.add(port)

    def render(self) -> str:
        cells = set(self.nodes) | set(self.wires)
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


def thisthat(truth_table: str) -> str:
    """Return a planar thisthat decision tree with linear source area."""
    n = _validate_truth_table(truth_table)
    if n == 0:
        return f"▣─{'■' if truth_table == '1' else '□'}═◇"
    builder = _Builder()
    axes = ((1, 0), (0, 1))

    def span(level: int) -> int:
        return 8 * (1 << ((n - level - 1) // 2)) - 2

    def tree(
        level: int,
        lo: int,
        hi: int,
        pop: tuple[int, int],
        incoming: tuple[int, int],
    ) -> None:
        if hi - lo == 1:
            builder.node(pop, "■" if truth_table[lo] == "1" else "□")
            output = (pop[0] + 2 * incoming[0], pop[1] + 2 * incoming[1])
            builder.node(output, "◇")
            builder.connect(_path(pop, output, incoming[0] != 0), "double")
            return
        builder.node(pop, "◧")
        router = (pop[0] + 2 * incoming[0], pop[1] + 2 * incoming[1])
        axis = axes[level % 2]
        builder.node(router, "◑" if axis[0] else "◒")
        builder.connect(_path(pop, router, incoming[0] != 0), "double")
        mid = (lo + hi) // 2
        for sign, child_lo, child_hi in ((-1, lo, mid), (1, mid, hi)):
            child_incoming = (sign * axis[0], sign * axis[1])
            child = (
                router[0] + span(level) * child_incoming[0],
                router[1] + span(level) * child_incoming[1],
            )
            builder.connect(_path(router, child, axis[0] != 0), "single")
            tree(level + 1, child_lo, child_hi, child, child_incoming)

    root = (0, 0)
    tree(0, 0, len(truth_table), root, (0, 1))
    min_x = min(x for x, _ in set(builder.nodes) | set(builder.wires))
    min_y = min(y for _, y in set(builder.nodes) | set(builder.wires))
    loader_y = min_y - 4
    start_x = min_x - 4 * n - 4
    builder.node((start_x, loader_y), "▣")
    previous = (start_x, loader_y)
    for i in range(n):
        diamond = (start_x + 2 + 4 * i, loader_y)
        push = (diamond[0] + 2, loader_y)
        builder.node(diamond, "◇")
        builder.node(push, "◨")
        builder.connect(_path(previous, diamond, True), "single")
        builder.connect(_path(diamond, push, True), "double")
        previous = push
    entry = (root[0], root[1] - 1)
    route = _path(previous, (root[0], loader_y), True)
    route += _path((root[0], loader_y), entry, False)[1:]
    route.append(root)
    builder.connect(route, "single")
    return builder.render()
