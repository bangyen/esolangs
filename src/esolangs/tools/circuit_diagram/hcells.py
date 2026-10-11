"""Cell guards for H trees, whose total attempted wire length is O(T)."""

from itertools import pairwise

from .layout import _HOLD, _Layout, _RoutingLayout


class _HCellLayout(_RoutingLayout):
    """Route H wires without inserting points into sorted shared-axis lists.

    With r inputs left, there are O(T/2**r) sites, O(r) wires per hop,
    and O(2**(r/2) + r) cells per wire. Their length sum is O(T).
    Cell dictionaries therefore cost expected O(T) work and O(T) space;
    this bound does not apply to unrestricted shared-DAG layouts.
    """

    def __init__(self, width: int) -> None:
        super().__init__()
        self._width = width
        self._horizontal_cells: dict[int, int] = {}
        self._vertical_cells: dict[int, int] = {}
        self._glyph_cells: set[int] = set()
        self._junction_cells: dict[int, int] = {}
        self._reserved_cells: dict[int, int] = {}

    def _key(self, x: int, y: int) -> int:
        if not 0 <= x < self._width or y < 0:
            raise AssertionError(f"H coordinate outside its width: {(x, y)}")
        return y * self._width + x

    def glyph(self, x: int, y: int, char: str) -> None:
        key = self._key(x, y)
        if (
            key in self._glyph_cells
            or key in self._horizontal_cells
            or key in self._vertical_cells
        ):
            raise AssertionError(f"H glyph collision at {(x, y)}")
        self._glyph_cells.add(key)
        self.glyphs[x, y] = char

    def junction(self, x: int, y: int, signal: int) -> None:
        key = self._key(x, y)
        if (
            key in self._glyph_cells
            or self._horizontal_cells.get(key, signal) != signal
            or self._vertical_cells.get(key, signal) != signal
            or self._junction_cells.get(key, signal) != signal
        ):
            raise AssertionError(f"H junction collision at {(x, y)}")
        self._junction_cells[key] = signal
        self.junctions[x, y] = signal

    def reserve(self, point: tuple[int, int], signal: int) -> None:
        self._reserved_cells[self._key(*point)] = signal

    def release(self, signal: int) -> None:
        self._reserved_cells = {
            key: owner for key, owner in self._reserved_cells.items() if owner != signal
        }

    def run_horizontal(self, x0: int, x1: int, y: int, signal: int) -> None:
        lo, hi = min(x0, x1) + 1, max(x0, x1)
        self._key(min(x0, x1), y)
        self._key(max(x0, x1), y)
        offset = y * self._width
        cells, glyphs = self._horizontal_cells, self._glyph_cells
        for key in range(offset + lo, offset + hi):
            if key in glyphs or cells.get(key, signal) != signal:
                raise AssertionError(f"H horizontal collision at cell {key}")
            cells[key] = signal
        if lo < hi:
            self.horizontal.setdefault(y, []).append((lo, hi, signal))

    def run_vertical(self, x: int, y0: int, y1: int, signal: int) -> None:
        lo, hi = min(y0, y1) + 1, max(y0, y1)
        self._key(x, min(y0, y1))
        self._key(x, max(y0, y1))
        cells, glyphs, width = (
            self._vertical_cells,
            self._glyph_cells,
            self._width,
        )
        for key in range(lo * width + x, hi * width + x, width):
            if key in glyphs or cells.get(key, signal) != signal:
                raise AssertionError(f"H vertical collision at cell {key}")
            cells[key] = signal
        if lo < hi:
            self.vertical.setdefault(x, []).append((lo, hi, signal))

    def _route_is_free(self, points: list[tuple[int, int]], signal: int) -> bool:
        glyphs, holds, dots = (
            self._glyph_cells,
            self._reserved_cells,
            self._junction_cells,
        )
        horizontal, vertical, width = (
            self._horizontal_cells,
            self._vertical_cells,
            self._width,
        )
        for x, y in points:
            key = self._key(x, y)
            if (
                key in glyphs
                or holds.get(key, signal) != signal
                or horizontal.get(key, signal) != signal
                or vertical.get(key, signal) != signal
            ):
                return False
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    # Neighbours must not wrap across a packed row boundary.
                    if not 0 <= x + dx < width or y + dy < 0:
                        continue
                    neighbour = key + dy * width + dx
                    if (
                        dots.get(neighbour, signal) != signal
                        or holds.get(neighbour) == _HOLD
                    ):
                        return False
        for (x0, y0), (x1, y1) in pairwise(points):
            if x0 == x1:
                lo, hi = min(y0, y1) + 1, max(y0, y1)
                cells = vertical
                keys = range(lo * width + x0, hi * width + x0, width)
            else:
                lo, hi = min(x0, x1) + 1, max(x0, x1)
                cells = horizontal
                keys = range(y0 * width + lo, y0 * width + hi)
            for key in keys:
                if (
                    key in glyphs
                    or cells.get(key, signal) != signal
                    or holds.get(key, signal) != signal
                    or dots.get(key, signal) != signal
                ):
                    return False
        return True

    def seal(self) -> _Layout:
        """Return ordinary ordered intervals using linear coordinate buckets."""
        result = _Layout()
        result.glyphs, result.junctions = self.glyphs, self.junctions
        for source, destination in (
            (self.horizontal, result.horizontal),
            (self.vertical, result.vertical),
        ):
            buckets: dict[int, list[tuple[int, int, int]]] = {}
            for axis, runs in source.items():
                for start, end, signal in runs:
                    buckets.setdefault(start, []).append((axis, end, signal))
            for start in range(max(buckets, default=-1) + 1):
                for axis, end, signal in buckets.get(start, ()):
                    line = destination.setdefault(axis, [])
                    if line and line[-1][2] == signal and start <= line[-1][1]:
                        old_start, old_end, _ = line[-1]
                        line[-1] = old_start, max(old_end, end), signal
                    else:
                        line.append((start, end, signal))
        by_x: dict[int, list[int]] = {}
        by_y: dict[int, list[int]] = {}
        for x, y in self.glyphs:
            by_x.setdefault(x, []).append(y)
            by_y.setdefault(y, []).append(x)
        for x in range(max(by_x, default=-1) + 1):
            for y in by_x.get(x, ()):
                result._glyph_rows.setdefault(y, []).append(x)  # noqa: SLF001
        for y in range(max(by_y, default=-1) + 1):
            for x in by_y.get(y, ()):
                result._glyph_cols.setdefault(x, []).append(y)  # noqa: SLF001
        return result
