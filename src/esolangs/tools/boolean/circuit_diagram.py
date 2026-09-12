r"""Boolean-function generator for Circuit Diagram."""

from typing import Literal

from esolangs.tools.boolean.helpers import (
    _maybe_complement,
    _validate_truth_table,
    essential_inputs,
    minterm_literals,
    read_at,
)

# The gate characters this.
# minterm tree, and the two.
_GateGlyph = Literal["a", "o", "x", "X"]
_ConstGlyph = Literal["x", "X"]

__all__ = ["circuit_diagram"]

# Spacing.
# that no two junctions of.
# each other (see the module.
_COL_STEP = 2
_ROW_STEP = 2


class _Layout:
    r"""Wire segments and glyphs, rendered to characters only at the end."""

    def __init__(self) -> None:
        r"""Start an empty layout."""
        # Runs are half-open interior.
        # row -> [(x0, x1, signal)] and.
        self.horizontal: dict[int, list[tuple[int, int, int]]] = {}
        self.vertical: dict[int, list[tuple[int, int, int]]] = {}
        self.junctions: dict[tuple[int, int], int] = {}
        self.glyphs: dict[tuple[int, int], str] = {}
        # Glyph coordinates indexed.
        self._glyph_rows: dict[int, list[int]] = {}
        self._glyph_cols: dict[int, list[int]] = {}

    def glyph(self, x: int, y: int, char: str) -> None:
        r"""Place a literal character (a gate, an input dash, an output)."""
        self._check_free(x, y)
        self.glyphs[(x, y)] = char
        self._glyph_rows.setdefault(y, []).append(x)
        self._glyph_cols.setdefault(x, []).append(y)

    def junction(self, x: int, y: int, signal: int) -> None:
        r"""Place a ``.`` carrying ``signal``."""
        existing = self.junctions.get((x, y))
        if existing is not None and existing != signal:
            raise AssertionError(f"junctions of two signals meet at ({x}, {y})")
        self._check_free(x, y)
        self.junctions[(x, y)] = signal

    def run_horizontal(self, x0: int, x1: int, y: int, signal: int) -> None:
        r"""Record a horizontal run between two junctions, exclusive."""
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
        self.horizontal.setdefault(y, []).append((lo, hi, signal))

    def run_vertical(self, x: int, y0: int, y1: int, signal: int) -> None:
        r"""Record a vertical run between two junctions, exclusive."""
        lo, hi = min(y0, y1) + 1, max(y0, y1)
        if lo >= hi:
            return
        hit = self._clash(self.vertical.get(x), self._glyph_cols.get(x), lo, hi, signal)
        if hit is not None:
            y, wire = hit
            if wire:
                raise AssertionError(f"two signals run vertical through ({x}, {y})")
            raise AssertionError(f"wire crosses glyph at ({x}, {y})")
        self.vertical.setdefault(x, []).append((lo, hi, signal))

    @staticmethod
    def _clash(
        runs: list[tuple[int, int, int]] | None,
        glyph_line: list[int] | None,
        lo: int,
        hi: int,
        signal: int,
    ) -> tuple[int, bool] | None:
        r"""First cell of ``[lo, hi)`` claimed against ``signal``, if any."""
        hit: tuple[int, bool] | None = None
        for a, b, s in runs or ():
            if s != signal and a < hi and lo < b:
                at = max(lo, a)
                if hit is None or at < hit[0]:
                    hit = (at, True)
        for g in glyph_line or ():
            if lo <= g < hi and (hit is None or g < hit[0]):
                hit = (g, False)
        return hit

    def _check_free(self, x: int, y: int) -> None:
        r"""Reject placing a glyph or junction over a wire or another glyph."""
        if (x, y) in self.glyphs:
            raise AssertionError(f"two glyphs at ({x}, {y})")
        if any(a <= x < b for a, b, _ in self.horizontal.get(y, ())) or any(
            a <= y < b for a, b, _ in self.vertical.get(x, ())
        ):
            raise AssertionError(f"glyph at ({x}, {y}) lands on a wire")

    def _check_junction_spacing(self) -> None:
        r"""Reject two signals' junctions resting within one cell."""
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
        r"""Return the layout as text, deriving each cell from its coverage."""
        self._check_junction_spacing()

        height = 0
        for y in self.horizontal:
            height = max(height, y + 1)
        for runs in self.vertical.values():
            for _, b, _ in runs:
                height = max(height, b)
        for _, y in self.junctions:
            height = max(height, y + 1)
        for _, y in self.glyphs:
            height = max(height, y + 1)
        if height == 0:
            return ""  # pragma: no cover - every table lays a wire

        # Rightmost occupied cell per.
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


class _Builder:
    r"""Allocates buses and gate bands, and records their wiring."""

    def __init__(self) -> None:
        r"""Start an empty build."""
        self.layout = _Layout()
        self.next_column = 1
        self.next_row = 0
        self.next_signal = 0
        # signal id -> (column, topmost.
        self.buses: dict[int, tuple[int, int]] = {}
        # Gate column groups that may.
        # recyclable signal was cut.
        # entered here: an input rail.
        # minterm that selects them, so.
        # drawing, while the circuit.
        # result and each running ``o``.
        # gate on the next band down --.
        self.free_strides: list[int] = []
        self.stride_of: dict[int, int] = {}
        # Set once a width is asked.
        # and the width the bands have.
        # intermediate signal not yet.
        # in the order they were made.
        # and complements are not in.
        # left of ``band_start``, and.
        self.limit: int | None = None
        self.band_start = 0
        self.live: list[int] = []

    def _new_signal(self) -> int:
        r"""Return a fresh signal id."""
        signal = self.next_signal
        self.next_signal += 1
        return signal

    def _new_column(self) -> int:
        r"""Return a fresh bus column, right of every bus column in use."""
        column = self.next_column
        self.next_column += _COL_STEP
        return column

    def _gate_columns(self, after: int = -1) -> tuple[int, int]:
        r"""Reserve the columns one gate needs: its inputs, glyph, and output."""
        # A dead group is reused rather.
        # make that safe.
        # .
        # Rows: the drawing only ever.
        # increasing rows and ``_tap``.
        # recycled group's old wiring.
        # it last, and everything drawn.
        # below that.
        # .
        # Columns: the signal flows.
        # *right* of every bus it reads.
        # gate's row to the input.
        # group recycled to the left of.
        # the gate's own glyph cell --.
        # caught by :class:`_Layout`.
        # rightmost bus the gate will.
        usable = [group for group in self.free_strides if group + _COL_STEP > after]
        if usable:
            first = min(usable)
            self.free_strides.remove(first)
        else:
            first = self.next_column
            self.next_column += 3 * _COL_STEP
        return first, first + _COL_STEP

    def _band(self) -> None:
        r"""Start a fresh band of columns, carrying the live signals back left."""
        for offset, signal in enumerate(self.live):
            column = self.band_start + offset * _COL_STEP
            row = self._new_band()
            self._tap(signal, column, row)
            self.buses[signal] = (column, row)
        # A carried signal sits in a.
        # group, so releasing it gives.
        # though: a later band has to.
        # how this first went wrong --.
        # another signal while its bus.
        # :class:`_Layout` refused to.
        self.stride_of.clear()
        self.free_strides.clear()
        self.next_column = self.band_start + len(self.live) * _COL_STEP

    def _room(self, after: int) -> bool:
        r"""Whether a gate reading up to ``after`` fits without a new band."""
        if self.limit is None:
            return True
        if any(group + _COL_STEP > after for group in self.free_strides):
            return True
        return self.next_column + 3 * _COL_STEP <= self.limit

    def _release(self, signal: int) -> None:
        r"""Give back ``signal``'s column group, if it owns one to give."""
        stride = self.stride_of.pop(signal, None)
        if stride is not None:
            self.free_strides.append(stride)
        if signal in self.live:
            self.live.remove(signal)

    def _new_band(self) -> int:
        r"""Return the centre row of a fresh three-row gate band."""
        row = self.next_row + 1
        self.next_row += 2 + _ROW_STEP
        return row

    def input_bus(self) -> int:
        r"""Draw one input line and return the signal its bit arrives on."""
        signal = self._new_signal()
        column = self._new_column()
        row = self.next_row
        self.next_row += _ROW_STEP

        self.layout.glyph(0, row, "-")
        self.layout.run_horizontal(0, column, row, signal)
        self.layout.junction(column, row, signal)
        self.buses[signal] = (column, row)
        return signal

    def invert(self, source: int) -> int:
        r"""Return a signal carrying ``~source``, computed once."""
        if not self._room(self.buses[source][0]):
            self._band()
        _, column = self._gate_columns(self.buses[source][0])
        row = self._new_band()

        # ``~`` reads the cell level.
        # junction immediately to its.
        self._tap(source, column - 1, row)
        self.layout.glyph(column, row, "~")

        signal = self._new_signal()
        self.layout.junction(column + 1, row, signal)
        self.buses[signal] = (column + 1, row)
        return signal

    def gate(self, kind: _GateGlyph, left: int, right: int) -> int:
        r"""Place a two-input ``kind`` gate and return its output signal."""
        if not self._room(max(self.buses[left][0], self.buses[right][0])):
            self._band()
        first, column = self._gate_columns(
            max(self.buses[left][0], self.buses[right][0])
        )
        row = self._new_band()

        self._feed(left, column - 1, row - 1)
        self._feed(right, column - 1, row + 1)
        self.layout.glyph(column, row, kind)

        signal = self._new_signal()
        self.layout.junction(column + 1, row, signal)
        self.buses[signal] = (column + 1, row)
        self.stride_of[signal] = first
        if self.limit is not None:
            self.live.append(signal)
        self._release(left)
        self._release(right)
        return signal

    def constant(self, source: int, kind: _ConstGlyph) -> int:
        r"""Return a constant signal, from one bus fed to both gate inputs."""
        _, column = self._gate_columns(self.buses[source][0])
        row = self._new_band()

        self._tap(source, column - 1, row - 1)
        self.layout.run_vertical(column - 1, row - 1, row + 1, source)
        self.layout.junction(column - 1, row + 1, source)
        self.layout.glyph(column, row, kind)

        signal = self._new_signal()
        self.layout.junction(column + 1, row, signal)
        self.buses[signal] = (column + 1, row)
        return signal

    def output(self, source: int) -> None:
        r"""Draw the ``:`` that prints ``source``'s value."""
        column, row = self.buses[source]
        self.layout.glyph(column + 1, row, "-")
        self.layout.glyph(column + 2, row, ":")

    def _tap(self, signal: int, x: int, y: int) -> None:
        r"""Extend ``signal``'s bus down to row ``y`` and end it at ``(x, y)``."""
        column, reached = self.buses[signal]
        # Each leg is skipped when the.
        # column, which the layout.
        # gate and a bus column is its.
        # cell away on both axes.
        # that did reach a tap head-on.
        # run and a junction on top of.
        if y != reached:  # pragma: no branch - a tap is never on the bus row
            self.layout.run_vertical(column, reached, y, signal)
            self.layout.junction(column, y, signal)
            self.buses[signal] = (column, y)
        if x != column:  # pragma: no branch - nor in the bus column
            self.layout.run_horizontal(column, x, y, signal)
            self.layout.junction(x, y, signal)

    def _feed(self, signal: int, x: int, y: int) -> None:
        r"""Bring ``signal`` to a gate's input junction at ``(x, y)``."""
        self._tap(signal, x, y)


def _minterm(
    builder: _Builder, literals: list[tuple[int, int | None]], index: int
) -> int:
    r"""Return a signal that is 1 exactly when the inputs spell ``index``."""
    n = len(literals)
    chosen = []
    for position, wants_complement in minterm_literals(index, n):
        plain, negated = literals[position]
        if not wants_complement:
            chosen.append(plain)
        elif negated is None:
            raise AssertionError(f"input {position} needs its complement")
        else:
            chosen.append(negated)
    return _fold(builder, "a", chosen)


def _fold(builder: _Builder, glyph: _GateGlyph, parts: list[int]) -> int:
    r"""Combine ``parts`` with ``glyph`` gates, balanced rather than in a."""
    if len(parts) == 1:
        return parts[0]
    half = len(parts) // 2
    left = _fold(builder, glyph, parts[:half])
    return builder.gate(glyph, left, _fold(builder, glyph, parts[half:]))


def _circuit_diagram_at(truth_table: str, limit: int | None) -> str:
    r"""Build a Circuit Diagram program computing the given truth table."""
    _validate_truth_table(truth_table)

    builder = _Builder()
    n = len(truth_table).bit_length() - 1
    # Every input keeps its own.
    # the interface -- but a table.
    # table, and the cost here is.
    # per selected row, each a gate.
    # So the chains are built over.
    # ignored rail simply drives.
    # first already does for a.
    used = essential_inputs(truth_table, n) or [0]
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    rails = [builder.input_bus() for _ in range(n)]
    if len(used) < n:
        # Re-point at the surviving.
        # everything below is written.
        rails = [rails[i] for i in used]
        truth_table = table
        n = len(used)

    # A sum of minterms spends one.
    # more ones than zeros is.
    # inverted: every chain that.
    # constant table is excluded.
    # complementing it would only.
    if len(set(truth_table)) == 1:
        table, invert_result = truth_table, False
    else:
        table, invert_result = _maybe_complement(truth_table)
    minterms = [i for i, bit in enumerate(table) if bit == "1"]
    if not minterms:
        constant: _ConstGlyph | None = "x"
    elif len(minterms) == len(truth_table):
        constant = "X"
    else:
        constant = None

    if constant is not None:
        # A constant table is one.
        # literal at all, so building.
        # them driving a bus nothing.
        # here: every index is a.
        # complement is needed for a.
        result = builder.constant(rails[0], constant)
    else:
        # A complement is computed once.
        # selects it -- but only if one.
        # minterm (both inputs of an.
        # building one anyway leaves a.
        # plus the tap and the run out.
        needs_complement = [
            any(not (index >> (n - 1 - position)) & 1 for index in minterms)
            for position in range(n)
        ]
        literals: list[tuple[int, int | None]] = [
            (rail, builder.invert(rail) if needed else None)
            for rail, needed in zip(rails, needs_complement, strict=True)
        ]
        # The rails and complements are.
        # live for the whole drawing; a.
        # after them, which is why the.
        builder.band_start = builder.next_column
        builder.limit = limit

        def combine(lo: int, hi: int) -> int:
            r"""Sum ``minterms[lo:hi]`` as a balanced tree of ``o`` gates."""
            if hi - lo == 1:
                return _minterm(builder, literals, minterms[lo])
            mid = (lo + hi) // 2
            return builder.gate("o", combine(lo, mid), combine(mid, hi))

        result = combine(0, len(minterms))

    if invert_result:
        result = builder.invert(result)
    builder.output(result)
    return builder.layout.render()


def circuit_diagram(truth_table: str, width: int | None = None) -> str:
    r"""Build a Circuit Diagram program computing the given truth table."""
    flat = _circuit_diagram_at(truth_table, None)
    if width is None or max(len(line) for line in flat.split("\n")) <= width:
        return flat
    banded = _circuit_diagram_at(truth_table, width)
    if max(len(line) for line in banded.split("\n")) < max(
        len(line) for line in flat.split("\n")
    ):
        return banded
    return flat
