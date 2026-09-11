r"""Boolean-function generator for Circuit Diagram.

Circuit Diagram is a language for drawing boolean circuits, so a truth
table is its native idiom: the generated program is the sum of the table's
minterms, drawn as an ASCII gate network that reads one bit per input wire
and prints the answer through ``:``.

Layout
------

The geometry controls the program -- the language has no statements to
sequence, only cells that have to line up -- so the program is built as a
*model* of wire segments first and rendered to characters afterwards,
rather than painted cell by cell in draw order.

Every signal owns a vertical **bus column**; every gate owns a three-row
**band**.  A gate at ``(c, r)`` reads its two inputs from ``.`` cells at
``(c - 1, r - 1)`` and ``(c - 1, r + 1)`` and drives a ``.`` at
``(c + 1, r)`` -- the spec's own AND sample -- so each gate is fed by two
horizontal segments running from a bus column to its left-hand junctions,
and its result leaves along a fresh bus.

**Crossings are the point, not a hazard.**  A network where every input
feeds every minterm is not planar, so wires must cross; the language says
exactly what that looks like.  The spec's crossover figure puts ``-=-``
between two horizontal wires and ``|`` above and below, with "opposite
wires are connected", so one ``=`` carries a horizontal and a vertical wire
past each other independently.  The renderer therefore derives each cell
from what covers it: a horizontal segment alone is ``-``, a vertical
segment alone is ``|``, both together is ``=``, and an endpoint is ``.``.
The wiki's own prime tester is drawn the same way.

What the layout must still guarantee is that nothing *merges* by accident.
A ``.`` connects to all eight of its neighbours, so two junctions belonging
to different signals that come to rest diagonally adjacent silently become
one wiring.  The renderer checks that mechanically -- along with two
segments of different signals sharing a cell in the same direction -- and
raises rather than emitting a circuit that is wrong in a way only the truth
table would reveal.

Construction
------------

``truth_table`` is a binary string of length ``2**n`` indexed by the inputs
most significant first, matching the other generators in this package.

* ``n`` input bits arrive on ``n`` separate lines, each a ``-`` at the start
  of its own line, which is what the spec makes an input port.  Keeping the
  bits on separate lines rather than in one ``-n-`` multi-wire keeps the
  network scalar: the multi-wire path would need a ``<`` splitter tree to
  get back to individual rails, and the splitter's rounding rule makes that
  layout depend on ``n`` in a way this one does not.
* the **literal buses** -- each input, and each input's ``~`` where some
  minterm needs it -- are built once, up front.  A bus may be tapped by any
  number of gates: it is still one wiring with one driver, so fan-out costs
  nothing and no ``~`` is ever duplicated.  A complement no minterm selects
  is not built at all: an input whose bit is 1 in every minterm never reads
  it, and emitting one anyway leaves a ``~`` driving a bus nothing consumes,
  plus the tap and the run out to it.  AND needs no ``~`` at all, which
  takes its drawing from 324 characters to 144.
* each minterm (a row of the table whose entry is ``1``) is a chain of
  two-input ``a`` gates over the ``n`` literal buses its index selects;
* the minterms are combined by a chain of ``o`` gates, and the result runs
  into ``-:``.

**A dense table is drawn as its complement.**  The cost is one ``a`` chain
per row selected, so a table with more ones than zeros is built from its
*zero* rows and the result inverted -- one ``~``, however many chains that
saves.  It is the trade
:func:`~esolangs.tools.boolean.helpers._maybe_complement` makes for the
other sum-of-minterms generators, and it is worth more here, because a
chain is not one instruction but a gate per literal plus the runs feeding
it: a dense three-input table goes from ~7000 characters to ~190.  Choosing
by the *count* rather than per minterm also keeps the complement buses
honest -- which literals get a ``~`` is decided from the rows actually
drawn.

**Constant tables need no minterms.**  An all-zero table has none to sum and
an all-one table would need ``2**n`` of them, so both are emitted as a
single gate fed from one bus on both inputs: ``x`` of a value with itself is
always 0 and ``X`` of a value with itself is always 1.  Feeding one wiring
into both slots of a gate is the shape the wiki's own constant-output
circuit uses, and the interpreter accepts it for that reason.

**Every wiring is driven exactly once.**  A ``:`` prints in *every*
generation its wire carries a value, and a wiring driven twice takes the
XOR of its drivers, so a second driver would corrupt both the value and the
output length.  Each bus here is written by exactly one gate (or one input
port) and only ever read after that, which is why the tests can assert that
a run prints exactly one character.
"""

from typing import Literal

from esolangs.tools.boolean.helpers import (
    _maybe_complement,
    _validate_truth_table,
    essential_inputs,
    minterm_literals,
    read_at,
)

# The gate characters this generator draws: an AND and an OR for the
# minterm tree, and the two self-fed XOR forms for a constant table.
_GateGlyph = Literal["a", "o", "x", "X"]
_ConstGlyph = Literal["x", "X"]

__all__ = ["circuit_diagram"]

# Spacing.  Buses are two columns apart and gate bands two rows apart, so
# that no two junctions of different signals ever land within one cell of
# each other (see the module docstring's note on the eight-way ``.``).
_COL_STEP = 2
_ROW_STEP = 2


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
        self._glyph_rows.setdefault(y, []).append(x)
        self._glyph_cols.setdefault(x, []).append(y)

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
        self.horizontal.setdefault(y, []).append((lo, hi, signal))

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
        self.vertical.setdefault(x, []).append((lo, hi, signal))

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
        """Reject placing a glyph or junction over a wire or another glyph."""
        if (x, y) in self.glyphs:
            raise AssertionError(f"two glyphs at ({x}, {y})")
        if any(a <= x < b for a, b, _ in self.horizontal.get(y, ())) or any(
            a <= y < b for a, b, _ in self.vertical.get(x, ())
        ):
            raise AssertionError(f"glyph at ({x}, {y}) lands on a wire")

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


class _Builder:
    """Allocates buses and gate bands, and records their wiring.

    A *bus* is a vertical column carrying one signal, written once and read
    by any number of gates.  A gate occupies a three-row band and leaves its
    result on a fresh bus.
    """

    def __init__(self) -> None:
        """Start an empty build."""
        self.layout = _Layout()
        self.next_column = 1
        self.next_row = 0
        self.next_signal = 0
        # signal id -> (column, topmost row the bus has reached)
        self.buses: dict[int, tuple[int, int]] = {}
        # Gate column groups that may be handed out again, and the group each
        # recyclable signal was cut from.  Only a *gate's* output is ever
        # entered here: an input rail and a complement are read by every
        # minterm that selects them, so their columns stay live for the whole
        # drawing, while the circuit below is a left fold -- each ``a`` chain
        # result and each running ``o`` result is read exactly once, by the
        # gate on the next band down -- so those die as soon as they are read.
        self.free_strides: list[int] = []
        self.stride_of: dict[int, int] = {}

    def _new_signal(self) -> int:
        """Return a fresh signal id."""
        signal = self.next_signal
        self.next_signal += 1
        return signal

    def _new_column(self) -> int:
        """Return a fresh bus column, right of every bus column in use.

        Input rails only.  A rail is read by every minterm that selects it,
        so it is live for the whole drawing and its column is never given
        back; :func:`_gate_columns` is where the recycling happens.

        A gate is drawn one column left of the bus it drives and reads its
        inputs one column left of *that*, so the columns a gate occupies
        must be clear of every existing bus: a bus running vertically
        through the gate's input junction would carry the gate's own output
        back to its input, making one wiring of both -- which the
        interpreter rejects, since a wiring may not touch both.
        """
        column = self.next_column
        self.next_column += _COL_STEP
        return column

    def _gate_columns(self, after: int = -1) -> tuple[int, int]:
        """Reserve the columns one gate needs: its inputs, glyph, and output.

        Three consecutive columns are taken at once -- the input junctions,
        the gate itself, and the bus it drives -- so no earlier bus can run
        down through any of them.
        """
        # A dead group is reused rather than a fresh one taken.  Two things
        # make that safe.
        #
        # Rows: the drawing only ever moves *down*.  ``_new_band`` hands out
        # increasing rows and ``_tap`` only extends a bus downward, so a
        # recycled group's old wiring ends at the row of the gate that read
        # it last, and everything drawn into it afterwards starts a band
        # below that.
        #
        # Columns: the signal flows left to right, and a gate must sit to the
        # *right* of every bus it reads.  ``_tap`` runs the bus along the
        # gate's row to the input junction one column left of the glyph, so a
        # group recycled to the left of a source would have that run cross
        # the gate's own glyph cell -- which is how this first went wrong,
        # caught by :class:`_Layout` refusing to draw it.  ``after`` is the
        # rightmost bus the gate will read, and only a group past it will do.
        usable = [group for group in self.free_strides if group + _COL_STEP > after]
        if usable:
            first = min(usable)
            self.free_strides.remove(first)
        else:
            first = self.next_column
            self.next_column += 3 * _COL_STEP
        return first, first + _COL_STEP

    def _release(self, signal: int) -> None:
        """Give back ``signal``'s column group, if it owns one to give.

        Called once the signal has been read into the gate that consumes
        it.  A rail or a complement is not in :attr:`stride_of` at all and
        so is never released; a gate output is removed as it is released, so
        a second call cannot hand the same group out twice.
        """
        stride = self.stride_of.pop(signal, None)
        if stride is not None:
            self.free_strides.append(stride)

    def _new_band(self) -> int:
        """Return the centre row of a fresh three-row gate band."""
        row = self.next_row + 1
        self.next_row += 2 + _ROW_STEP
        return row

    def input_bus(self) -> int:
        """Draw one input line and return the signal its bit arrives on.

        The spec makes a ``-`` at the start of a line an input port, so each
        input owns a row of its own; the rows are taken in order, which is
        the order the interpreter reads the bits in.

        One bus column is enough.  An input port draws only the ``-`` and
        the junction its bus starts from -- there is no gate glyph, nothing
        to its left to read, and no separate output column -- so reserving a
        whole gate's three columns, as this once did, left two empty
        columns per input that every later wire then had to run across.
        """
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
        """Return a signal carrying ``~source``, computed once."""
        _, column = self._gate_columns(self.buses[source][0])
        row = self._new_band()

        # ``~`` reads the cell level with it, so the tap has to end on the
        # junction immediately to its left rather than short of it.
        self._tap(source, column - 1, row)
        self.layout.glyph(column, row, "~")

        signal = self._new_signal()
        self.layout.junction(column + 1, row, signal)
        self.buses[signal] = (column + 1, row)
        return signal

    def gate(self, kind: _GateGlyph, left: int, right: int) -> int:
        """Place a two-input ``kind`` gate and return its output signal.

        The group is taken before the inputs are read and the inputs are
        released after, so a gate can never be handed the very group it is
        about to read out of.
        """
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
        self._release(left)
        self._release(right)
        return signal

    def constant(self, source: int, kind: _ConstGlyph) -> int:
        """Return a constant signal, from one bus fed to both gate inputs.

        ``x`` of a value with itself is always 0 and ``X`` always 1, so a
        constant table needs no minterms.  Both of the gate's inputs come
        from the same bus, which the interpreter accepts because the wiki's
        own constant-output circuit is drawn that way.
        """
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
        """Draw the ``:`` that prints ``source``'s value.

        ``:`` reads only a ``-`` directly to its left, so the signal is
        handed one cell along from the junction its bus already ends on.

        No band or gate columns are reserved for it.  ``:`` is two glyphs
        with nothing above, below, or left of them to keep clear, and the
        bus it reads is the last one built -- so its own row is free to the
        right by construction.  Taking a fresh band instead, as this once
        did, put the output three rows below the gate that drives it and ran
        the bus down to meet it, which is most of the staircase a small
        circuit used to end on.
        """
        column, row = self.buses[source]
        self.layout.glyph(column + 1, row, "-")
        self.layout.glyph(column + 2, row, ":")

    def _tap(self, signal: int, x: int, y: int) -> None:
        """Extend ``signal``'s bus down to row ``y`` and end it at ``(x, y)``.

        The bus runs down its own column to the target row, then along that
        row to ``x``.  Both legs carry the same signal as the bus, so the
        whole path is one wiring -- a tap reads the bus, it does not drive
        it.
        """
        column, reached = self.buses[signal]
        # Each leg is skipped when the bus already sits on the tap's row or
        # column, which the layout never produces: rows advance for every
        # gate and a bus column is its own, so a tap is always at least one
        # cell away on both axes.  Both tests stay, since a layout change
        # that did reach a tap head-on would otherwise draw a zero-length
        # run and a junction on top of the bus.
        if y != reached:  # pragma: no branch - a tap is never on the bus row
            self.layout.run_vertical(column, reached, y, signal)
            self.layout.junction(column, y, signal)
            self.buses[signal] = (column, y)
        if x != column:  # pragma: no branch - nor in the bus column
            self.layout.run_horizontal(column, x, y, signal)
            self.layout.junction(x, y, signal)

    def _feed(self, signal: int, x: int, y: int) -> None:
        """Bring ``signal`` to a gate's input junction at ``(x, y)``."""
        self._tap(signal, x, y)


def _minterm(
    builder: _Builder, literals: list[tuple[int, int | None]], index: int
) -> int:
    """Return a signal that is 1 exactly when the inputs spell ``index``.

    ``literals`` holds, per input position, the ``(plain, negated)`` bus
    signals; the bits of ``index`` choose which of each pair to AND.  The
    negated half is ``None`` when no minterm needs that input's complement,
    in which case this never selects it (see :func:`circuit_diagram`).
    """
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
    result = chosen[0]
    for literal in chosen[1:]:
        result = builder.gate("a", result, literal)
    return result


def circuit_diagram(truth_table: str) -> str:
    """Build a Circuit Diagram program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The program is the table's sum of minterms: one ``-`` input line per
    bit, a bus per literal, an ``a`` chain per table row that is a 1, an
    ``o`` chain combining them, and a ``:`` printing the result.  A constant
    table is emitted as a single self-fed gate instead.

    A table with more ones than zeros is built from its *zero* rows and the
    result inverted, since the cost is one chain per row selected and a
    ``~`` is one gate however many chains it saves -- the same trade
    :func:`~esolangs.tools.boolean.helpers._maybe_complement` makes for the
    other sum-of-minterms generators.  It is worth more here than there: a
    chain is a gate per literal plus the runs feeding it, so a dense
    three-input table drops from ~7000 characters to ~130.

    The drawing's *width* is gate column groups, and a group is reused once
    the bus it drives is dead.  What makes so many die is the shape of the
    circuit rather than any analysis: only the rails and their complements
    are read more than once, and everything else is a left fold -- each
    ``a`` chain result and each running ``o`` result is read exactly once,
    by the gate on the next band down -- so a group is free again one band
    after it is taken.  A gate must still sit right of every bus it reads,
    since the run feeding it travels along its row, so what is reused is the
    leftmost dead group past those buses.  Four inputs: 219 columns to 99.
    """
    _validate_truth_table(truth_table)

    builder = _Builder()
    n = len(truth_table).bit_length() - 1
    # Every input keeps its own ``-`` row -- the rows are the read order and
    # the interface -- but a table that ignores some of them is a smaller
    # table, and the cost here is entirely in the *body*: one ``a`` chain
    # per selected row, each a gate per literal plus the runs feeding it.
    # So the chains are built over the essential inputs' rails only, and an
    # ignored rail simply drives nothing, exactly as every rail but the
    # first already does for a constant table.
    used = essential_inputs(truth_table, n) or [0]
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    rails = [builder.input_bus() for _ in range(n)]
    if len(used) < n:
        # Re-point at the surviving rails and evaluate the reduced table;
        # everything below is written against ``rails``/``truth_table``.
        rails = [rails[i] for i in used]
        truth_table = table
        n = len(used)

    # A sum of minterms spends one ``a`` chain per 1-row, so a table with
    # more ones than zeros is cheaper built from its *zero* rows and
    # inverted: every chain that saves costs a share of one ``~``.  A
    # constant table is excluded because it is already a single gate, and
    # complementing it would only swap which glyph that gate uses.
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
        # A constant table is one self-fed gate over ``rails[0]``; it reads no
        # literal at all, so building the complements would leave every one of
        # them driving a bus nothing consumes.  (An all-ones table is the trap
        # here: every index is a minterm, so a per-minterm test concludes no
        # complement is needed for a table that reads none of them either way.)
        result = builder.constant(rails[0], constant)
    else:
        # A complement is computed once and shared by every minterm that
        # selects it -- but only if one does.  An input whose bit is 1 in every
        # minterm (both inputs of an AND, say) never reads its ``~``, and
        # building one anyway leaves a gate driving a bus nothing consumes,
        # plus the tap and the run out to it.
        needs_complement = [
            any(not (index >> (n - 1 - position)) & 1 for index in minterms)
            for position in range(n)
        ]
        literals: list[tuple[int, int | None]] = [
            (rail, builder.invert(rail) if needed else None)
            for rail, needed in zip(rails, needs_complement, strict=True)
        ]
        result = _minterm(builder, literals, minterms[0])
        for index in minterms[1:]:
            result = builder.gate("o", result, _minterm(builder, literals, index))

    if invert_result:
        result = builder.invert(result)
    builder.output(result)
    return builder.layout.render()
