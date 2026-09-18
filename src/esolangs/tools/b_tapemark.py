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

    def node(
        self,
        table: str,
        depth: int,
        x: int,
        y: int,
        start: int = 0,
        stop: int | None = None,
    ) -> None:
        """Place one branch and its descendants."""
        if stop is None:
            stop = len(table)
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
            for point, result in ((zero, table[start]), (one, table[start + 1])):
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
        middle = (start + stop) // 2
        self.node(table, depth - 1, x + 12, y - gap, start, middle)
        self.node(table, depth - 1, x + 12, y + gap, middle, stop)

    def render(self, *, reflect: bool = False) -> str:
        """Render after removing wholly blank rows and columns.

        ``reflect`` mirrors the program horizontally, directional symbols
        included.  Each row is drawn from its own cells, only as long as
        its last one, so the cost is the output's size rather than the
        bounding box (rows by the ``12n`` columns).
        """
        xs = sorted({x for x, _ in self.cells})
        ys = sorted({y for _, y in self.cells})
        column = {x: len(xs) - 1 - i if reflect else i for i, x in enumerate(xs)}
        symbols = {">": "<", "<": ">", "/": "\\", "\\": "/"} if reflect else {}
        rows: dict[int, dict[int, str]] = {y: {} for y in ys}
        for (x, y), char in self.cells.items():
            rows[y][column[x]] = symbols.get(char, char)
        lines = []
        for y in ys:
            cells = rows[y]
            line = [" "] * (max(cells) + 1)
            for i, char in cells.items():
                line[i] = char
            lines.append("".join(line))
        return "\n".join(lines)


def b_tapemark(truth_table: str, width: int | None = None) -> str:
    """Build a B-tapemark program computing ``truth_table``.

    The tree is reflected before rendering.  Its long branch corridors then
    occupy trailing rather than leading blanks, so ``rstrip`` removes them;
    the remaining text is linear in the tree rather than its bounding box.
    """
    depth = _validate_truth_table(truth_table)
    builder = _Builder()
    builder.put(-1, 0, ">")
    builder.node(truth_table, depth, 0, 0)
    if width is not None:
        # The raw orientation is the alternate width-requested layout.  Both
        # orientations have the same intrinsic width; only their ragged area
        # differs, so neither can honour a bound the other cannot.
        return builder.render()
    # Digits only print while travelling horizontally, so a quarter-turn is
    # not equivalent.  Reflection preserves every heading while moving the
    # tree's triangular padding to the right edge, where it is not rendered.
    return builder.render(reflect=True)
