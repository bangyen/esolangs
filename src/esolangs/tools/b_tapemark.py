"""Boolean-function generator for B-tapemark."""

from __future__ import annotations

from dataclasses import dataclass, field

from esolangs.tools.helpers import _validate_truth_table


@dataclass
class _Builder:
    """Place a collision-free mirror-swap decision tree."""

    cells: dict[tuple[int, int], str] = field(default_factory=dict)

    def put(self, x: int, y: int, char: str) -> None:
        """Place ``char``, rejecting a conflicting placement."""
        previous = self.cells.setdefault((x, y), char)
        if previous != char:
            raise AssertionError(f"layout collision at {(x, y)}")

    def node(self, table: str, depth: int, x: int, y: int) -> None:
        """Place one branch and its descendants."""
        # ``*`` builds a backslash/% path on the blank grid.  A vertical 0
        # match swaps onto it, turns right, then swaps back; a 1 stays on the
        # source grid.  Both cases reach distinct rightward paths.
        for offset in range(3):
            self.put(x + offset, y, "|")
        placements = {
            (3, 0): "\\",
            (3, 1): "|",
            (3, 2): "*",
            (3, 3): "\\",
            (3, 4): "\\",
            (4, 4): "|",
            (5, 4): "*",
            (6, 4): "%",
            (7, 4): "/",
            (7, 3): "|",
            (7, 2): "\\",
            (6, 2): "|",
            (5, 2): "-",
            (4, 2): "\\",
            (4, -2): "/",
            (10, -2): "\\",
            (10, -1): "0",
            (10, 0): "\\",
        }
        for (dx, dy), char in placements.items():
            self.put(x + dx, y + dy, char)

        zero = (x + 11, y - 1)
        one = (x + 11, y)
        if depth == 1:
            half = len(table) // 2
            for point, result in ((zero, table[0]), (one, table[half])):
                self.put(*point, result)
                self.put(point[0] + 1, point[1], "!")
            return

        gap = 8 * 2 ** (depth - 1)
        for point, mirror, target_y in (
            (zero, "/", y - gap),
            (one, "\\", y + gap),
        ):
            self.put(*point, mirror)
            self.put(point[0], target_y, mirror)
        half = len(table) // 2
        self.node(table[:half], depth - 1, x + 12, y - gap)
        self.node(table[half:], depth - 1, x + 12, y + gap)

    def render(self) -> str:
        """Render after removing wholly blank rows and columns."""
        xs = sorted({x for x, _ in self.cells})
        ys = sorted({y for _, y in self.cells})
        return "\n".join(
            "".join(self.cells.get((x, y), " ") for x in xs).rstrip() for y in ys
        )


def _reflect(source: str) -> str:
    """Reflect a program horizontally, including directional symbols."""
    symbols = str.maketrans({">": "<", "<": ">", "/": "\\", "\\": "/"})
    rows = source.splitlines()
    width = max(map(len, rows))
    return "\n".join(row.ljust(width)[::-1].translate(symbols).rstrip() for row in rows)


def b_tapemark(truth_table: str, width: int | None = None) -> str:
    """Build a B-tapemark program computing ``truth_table``."""
    depth = _validate_truth_table(truth_table)
    builder = _Builder()
    builder.put(-1, 0, ">")
    builder.node(truth_table, depth, 0, 0)
    program = builder.render()
    if width is None:
        return program
    # Digits only print while travelling horizontally, so a quarter-turn is
    # not equivalent. Reflection preserves the tree's intrinsic width while
    # making a supplied layout distinct from the raw one.
    return _reflect(program)
