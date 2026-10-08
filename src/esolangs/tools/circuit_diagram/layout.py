"""Wire layouts shared by the Circuit Diagram generators."""

from bisect import bisect_left, insort
from itertools import pairwise
from typing import Literal

# Owner of a reserved result anchor; no real signal may route through it.
_HOLD = -1

_Shape = Literal["down", "across", "under"]


class _Layout:
    """Wire segments and glyphs, rendered to characters only at the end.

    Segments are recorded with the signal they carry so the renderer can
    tell a legitimate crossing (two different signals, drawn ``=``) from a
    collision (two segments of different signals running the same way
    through one cell, which would merge them).

    A run is stored as one interval, not cell by cell: taps grow linearly
    with the drawing, so per-cell tables cost quadratic time and memory --
    n=9 held ~20M dict entries and n=10 would not fit.  The collision
    checks compare intervals instead, and the renderer paints them with
    slice assignment.
    """

    def __init__(self) -> None:
        """Start an empty layout."""
        # Runs are half-open interior intervals keyed by the fixed axis:
        # row -> [(x0, x1, signal)] and column -> [(y0, y1, signal)].
        self.horizontal: dict[int, list[tuple[int, int, int]]] = {}
        self.vertical: dict[int, list[tuple[int, int, int]]] = {}
        self.junctions: dict[tuple[int, int], int] = {}
        self.glyphs: dict[tuple[int, int], str] = {}
        # Glyph coordinates indexed both ways, for the run/glyph checks.
        self._glyph_rows: dict[int, list[int]] = {}
        self._glyph_cols: dict[int, list[int]] = {}

    def glyph(self, x: int, y: int, char: str) -> None:
        """Place a literal character (a gate, an input dash, an output)."""
        self._check_free(x, y)
        self.glyphs[(x, y)] = char
        insort(self._glyph_rows.setdefault(y, []), x)
        insort(self._glyph_cols.setdefault(x, []), y)

    def junction(self, x: int, y: int, signal: int) -> None:
        """Place a ``.`` carrying ``signal``."""
        existing = self.junctions.get((x, y))
        if existing is not None and existing != signal:
            raise AssertionError(f"junctions of two signals meet at ({x}, {y})")
        self._check_free(x, y)
        self.junctions[(x, y)] = signal

    def run_horizontal(self, x0: int, x1: int, y: int, signal: int) -> None:
        """Record a horizontal run between two junctions, exclusive."""
        lo, hi = min(x0, x1) + 1, max(x0, x1)
        if lo >= hi:
            return
        hit = self._clash(
            self.horizontal.get(y), self._glyph_rows.get(y), lo, hi, signal
        )
        if hit is not None:
            x, wire = hit
            if wire:
                raise AssertionError(f"two signals run horizontal through ({x}, {y})")
            raise AssertionError(f"wire crosses glyph at ({x}, {y})")
        self._record(self.horizontal.setdefault(y, []), (lo, hi, signal))

    def run_vertical(self, x: int, y0: int, y1: int, signal: int) -> None:
        """Record a vertical run between two junctions, exclusive."""
        lo, hi = min(y0, y1) + 1, max(y0, y1)
        if lo >= hi:
            return
        hit = self._clash(self.vertical.get(x), self._glyph_cols.get(x), lo, hi, signal)
        if hit is not None:
            y, wire = hit
            if wire:
                raise AssertionError(f"two signals run vertical through ({x}, {y})")
            raise AssertionError(f"wire crosses glyph at ({x}, {y})")
        self._record(self.vertical.setdefault(x, []), (lo, hi, signal))

    @staticmethod
    def _record(runs: list[tuple[int, int, int]], run: tuple[int, int, int]) -> None:
        """Insert an interval, taking O(1) for the builder's ordered runs."""
        if runs and runs[-1][2] == run[2] and run[0] <= runs[-1][1]:
            a, b, signal = runs[-1]
            runs[-1] = (min(a, run[0]), max(b, run[1]), signal)
            return
        if not runs or runs[-1] <= run:
            runs.append(run)
        else:  # layout-guard tests may deliberately insert out of order
            insort(runs, run)

    @staticmethod
    def _clash(
        runs: list[tuple[int, int, int]] | None,
        glyph_line: list[int] | None,
        lo: int,
        hi: int,
        signal: int,
    ) -> tuple[int, bool] | None:
        """First cell of ``[lo, hi)`` claimed against ``signal``, if any.

        Returns the offending coordinate along the run's axis and whether
        the clash is another signal's wire (``True``) or a glyph.
        """
        hit: tuple[int, bool] | None = None
        ordered = runs or []
        index = max(0, bisect_left(ordered, (lo, -1, -1)) - 1)
        while index < len(ordered):
            a, b, s = ordered[index]
            if a >= hi:
                break
            if s != signal and lo < b:
                at = max(lo, a)
                if hit is None or at < hit[0]:
                    hit = (at, True)
            index += 1
        glyphs = glyph_line or []
        index = bisect_left(glyphs, lo)
        while index < len(glyphs):
            g = glyphs[index]
            if g >= hi:
                break
            if hit is None or g < hit[0]:
                hit = (g, False)
            index += 1
        return hit

    def _check_free(self, x: int, y: int) -> None:
        """Reject placing a glyph or junction over a wire or another glyph."""
        if (x, y) in self.glyphs:
            raise AssertionError(f"two glyphs at ({x}, {y})")
        if self._covered(self.horizontal.get(y), x) or self._covered(
            self.vertical.get(x), y
        ):
            raise AssertionError(f"glyph at ({x}, {y}) lands on a wire")

    @staticmethod
    def _covered(runs: list[tuple[int, int, int]] | None, point: int) -> bool:
        """Whether a sorted interval line covers ``point``."""
        if not runs:
            return False
        index = bisect_left(runs, (point + 1, -1, -1)) - 1
        return index >= 0 and runs[index][0] <= point < runs[index][1]

    def _check_junction_spacing(self) -> None:
        """Reject two signals' junctions resting within one cell.

        A ``.`` connects to all eight of its neighbours, so two junctions
        carrying different signals that end up adjacent -- diagonally
        included -- merge into a single wiring.  Checking it here catches
        the whole class at once, rather than relying on the spacing
        constants to be large enough in every case.
        """
        for (x, y), signal in self.junctions.items():
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    other = self.junctions.get((x + dx, y + dy))
                    if other is not None and other != signal:
                        raise AssertionError(
                            f"junctions of different signals touch at "
                            f"({x}, {y}) and ({x + dx}, {y + dy})",
                        )

    def render(self) -> str:
        """Return the layout as text, deriving each cell from its coverage.

        Cell priority is glyph, then junction ``.``, then the wires: a
        horizontal and a vertical sharing a cell is a crossover ``=`` (the
        spec connects "opposite wires" across it), either alone is ``-`` or
        ``|``.  Rows are painted into byte buffers -- horizontal runs by
        slice, everything else point by point -- and cut at their last
        occupied cell, which is what per-cell ``rstrip`` did: every covered
        cell renders non-space.
        """
        self._check_junction_spacing()

        height = max(
            [y + 1 for y in self.horizontal]
            + [b for runs in self.vertical.values() for _, b, _ in runs]
            + [y + 1 for _, y in self.junctions]
            + [y + 1 for _, y in self.glyphs],
            default=0,
        )
        if height == 0:
            return ""  # pragma: no cover - every table lays a wire

        # Rightmost occupied cell per row, and the point features by row.
        last = [-1] * height
        verts: dict[int, list[int]] = {}
        for x, runs in self.vertical.items():
            for a, b, _ in runs:
                for y in range(a, b):
                    verts.setdefault(y, []).append(x)
                    if x > last[y]:
                        last[y] = x
        for y, runs in self.horizontal.items():
            edge = max(b for _, b, _ in runs) - 1
            if edge > last[y]:
                last[y] = edge
        dots: dict[int, list[int]] = {}
        for x, y in self.junctions:
            dots.setdefault(y, []).append(x)
            if x > last[y]:
                last[y] = x
        marks: dict[int, list[tuple[int, int]]] = {}
        for (x, y), char in self.glyphs.items():
            marks.setdefault(y, []).append((x, ord(char)))
            if x > last[y]:
                last[y] = x

        dash, pipe, cross, dot = ord("-"), ord("|"), ord("="), ord(".")
        dashes = b"-" * (max(last) + 1)
        spaces = b" " * (max(last) + 1)
        rows = []
        for y in range(height):
            edge = last[y]
            if edge < 0:
                rows.append("")
                continue
            buf = bytearray(spaces[: edge + 1])
            for a, b, _ in self.horizontal.get(y, ()):
                buf[a:b] = dashes[: b - a]
            for x in verts.get(y, ()):
                buf[x] = cross if buf[x] == dash or buf[x] == cross else pipe
            for x in dots.get(y, ()):
                buf[x] = dot
            for x, code in marks.get(y, ()):
                buf[x] = code
            rows.append(buf.decode("ascii"))
        return "\n".join(rows)


class _RoutingLayout(_Layout):
    """Layout whose wires are laid in fixed shapes over interval runs.

    The base class stores each run as one interval; this subclass used to
    also mirror every covered cell into ``_horizontal_cells`` /
    ``_vertical_cells`` so a route could be tested cell by cell.  That is
    O(area) time and memory for checks interval overlap answers in
    O(log runs + overlaps), and the H-layout's area is linear in the table,
    so the per-cell maps put a large constant on every build.  Junctions
    and reservations are indexed per row and column for the same reason.
    """

    def __init__(self) -> None:
        super().__init__()
        self._reserved: dict[tuple[int, int], int] = {}
        self._junction_rows: dict[int, list[tuple[int, int]]] = {}
        self._junction_cols: dict[int, list[tuple[int, int]]] = {}
        self._reserved_rows: dict[int, list[tuple[int, int]]] = {}
        self._reserved_cols: dict[int, list[tuple[int, int]]] = {}

    @staticmethod
    def _strip(line: list[tuple[int, int]], coord: int) -> None:
        """Drop the entry at ``coord`` from an indexed line, if present."""
        index = bisect_left(line, (coord, -1))
        while index < len(line) and line[index][0] == coord:
            line.pop(index)

    def reserve(self, point: tuple[int, int], signal: int) -> None:
        """Keep a future junction clear for ``signal`` while routing."""
        previous = self._reserved.get(point)
        if previous == signal:
            return
        x, y = point
        self._reserved[point] = signal
        if previous is not None:
            self._strip(self._reserved_rows[y], x)
            self._strip(self._reserved_cols[x], y)
        insort(self._reserved_rows.setdefault(y, []), (x, signal))
        insort(self._reserved_cols.setdefault(x, []), (y, signal))

    def release(self, signal: int) -> None:
        """Drop every reservation held by ``signal``."""
        self._reserved = {
            point: owner for point, owner in self._reserved.items() if owner != signal
        }
        self._reserved_rows = {}
        self._reserved_cols = {}
        for (x, y), owner in self._reserved.items():
            insort(self._reserved_rows.setdefault(y, []), (x, owner))
            insort(self._reserved_cols.setdefault(x, []), (y, owner))

    @staticmethod
    def _other_covering(
        runs: list[tuple[int, int, int]] | None, point: int, signal: int
    ) -> bool:
        """Whether an interval run of another signal covers ``point``."""
        if not runs:
            return False
        index = bisect_left(runs, (point + 1, -1, -1)) - 1
        return (
            index >= 0
            and runs[index][0] <= point < runs[index][1]
            and runs[index][2] != signal
        )

    @staticmethod
    def _indexed_clash(
        line: list[tuple[int, int]] | None, lo: int, hi: int, signal: int
    ) -> bool:
        """Whether an indexed point of another signal lies in ``[lo, hi)``."""
        if not line:
            return False
        index = bisect_left(line, (lo, -1))
        while index < len(line):
            coord, owner = line[index]
            if coord >= hi:
                return False
            if owner != signal:
                return True
            index += 1
        return False

    def junction(self, x: int, y: int, signal: int) -> None:
        """Place a junction unless another signal already occupies its cell."""
        existing = self.junctions.get((x, y))
        if (
            (existing is not None and existing != signal)
            or (x, y) in self.glyphs
            or self._other_covering(self.horizontal.get(y), x, signal)
            or self._other_covering(self.vertical.get(x), y, signal)
        ):
            raise AssertionError(f"junction collision at ({x}, {y})")
        if existing is None:
            insort(self._junction_rows.setdefault(y, []), (x, signal))
            insort(self._junction_cols.setdefault(x, []), (y, signal))
        self.junctions[(x, y)] = signal

    def run_horizontal(self, x0: int, x1: int, y: int, signal: int) -> None:
        """Record a horizontal run, checked against the interval runs."""
        lo, hi = min(x0, x1) + 1, max(x0, x1)
        hit = self._clash(
            self.horizontal.get(y), self._glyph_rows.get(y), lo, hi, signal
        )
        if hit is not None:
            raise AssertionError(f"horizontal collision at ({hit[0]}, {y})")
        self._record(self.horizontal.setdefault(y, []), (lo, hi, signal))

    def run_vertical(self, x: int, y0: int, y1: int, signal: int) -> None:
        """Record a vertical run, checked against the interval runs."""
        lo, hi = min(y0, y1) + 1, max(y0, y1)
        hit = self._clash(self.vertical.get(x), self._glyph_cols.get(x), lo, hi, signal)
        if hit is not None:
            raise AssertionError(f"vertical collision at ({x}, {hit[0]})")
        self._record(self.vertical.setdefault(x, []), (lo, hi, signal))

    def route(
        self,
        source: tuple[int, int],
        target: tuple[int, int],
        signal: int,
        shape: _Shape = "down",
    ) -> None:
        """Lay one wire in the given shape; the caller has chosen its lane.

        ``down`` runs along the source's column and then the target's row,
        ``across`` along the source's row and then the target's column, and
        ``under`` along the source's column to two rows past the target,
        across, and back up into it -- the shape that feeds a gate's lower
        input when a sibling wire already corners on the target's row.  The
        collision check is a guard on the layout's spacing rules, not a
        search: a wire that does not fit is a spacing bug.
        """
        sx, sy = source
        tx, ty = target
        if shape == "down":
            points = [source, (sx, ty), target]
        elif shape == "across":
            points = [source, (tx, sy), target]
        else:
            points = [source, (sx, ty + 2), (tx, ty + 2), target]
        if not self._route_is_free(points, signal):
            raise AssertionError(f"{shape} route from {source} to {target} collides")
        self._add_route(points, signal)

    def _add_route(self, points: list[tuple[int, int]], signal: int) -> None:
        """Add one already checked rectilinear route."""
        for point in points:
            self.junction(*point, signal)
        for (x0, y0), (x1, y1) in pairwise(points):
            if x0 == x1:
                self.run_vertical(x0, y0, y1, signal)
            else:
                self.run_horizontal(x0, x1, y0, signal)

    def _route_is_free(self, points: list[tuple[int, int]], signal: int) -> bool:
        """Whether a wire can be added without merging or overlapping signals."""
        for x, y in points:
            if (
                (x, y) in self.glyphs
                or self._reserved.get((x, y), signal) != signal
                or self._other_covering(self.horizontal.get(y), x, signal)
                or self._other_covering(self.vertical.get(x), y, signal)
            ):
                return False
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    other = self.junctions.get((x + dx, y + dy))
                    if other is not None and other != signal:
                        return False
                    if self._reserved.get((x + dx, y + dy)) == _HOLD:
                        return False
        for (x0, y0), (x1, y1) in pairwise(points):
            if x0 == x1:
                lo, hi = min(y0, y1) + 1, max(y0, y1)
                runs, glyphs = self.vertical.get(x0), self._glyph_cols.get(x0)
                reserved = self._reserved_cols.get(x0)
                junctions = self._junction_cols.get(x0)
            else:
                lo, hi = min(x0, x1) + 1, max(x0, x1)
                runs, glyphs = self.horizontal.get(y0), self._glyph_rows.get(y0)
                reserved = self._reserved_rows.get(y0)
                junctions = self._junction_rows.get(y0)
            if (
                self._clash(runs, glyphs, lo, hi, signal) is not None
                or self._indexed_clash(reserved, lo, hi, signal)
                or self._indexed_clash(junctions, lo, hi, signal)
            ):
                return False
        return True
