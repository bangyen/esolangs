r"""Boolean-function generator for Circuit Diagram.

Circuit Diagram is a language for drawing boolean circuits, so a truth
table is its native idiom.  The generated ASCII gate network reads one bit
per input wire, folds adjacent cofactors through muxes, and prints through
``:``.

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

**Crossings are the point, not a hazard.**  Shared selectors make the
network non-planar, so wires must cross.  The spec's crossover figure puts ``-=-``
between two horizontal wires and ``|`` above and below, with "opposite
wires are connected", so one ``=`` carries a horizontal and a vertical wire
past each other independently.  The renderer therefore derives each cell
from what covers it: a horizontal segment alone is ``-``, a vertical
segment alone is ``|``, both together is ``=``, and an endpoint is ``.``.

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
  of its own line, which is what the spec makes an input port.  Separate
  lines rather than one ``-n-`` multi-wire keep the network scalar: the
  multi-wire path would need a ``<`` splitter tree back to rails.
* each input and any complement the mux rules need is built once and shared;
* a left-to-right binary-carry fold combines adjacent cofactors.  Equal
  cofactors share one signal, ``0/1`` is the selector itself, and the other
  cases use a fixed one- or three-gate mux rule;
* a repeated subtree is built once (:func:`_dag`): the fold is hash-consed on
  ``(level, zero, one)`` and its bus is read by every parent, a bus fanning
  out freely.  A shared output keeps its column group until its last read.
  Area, 20 seeded tables: tiled from two blocks 0.69 / 0.49 / 0.41 of the
  unshared build at n=5 / 6 / 7, from four blocks 0.84 / 0.71 / 0.67, random
  tables 0.95 / 0.94 / 0.88;
* at most one unfinished signal per input level is live; the fold is one
  pass over the table and emits fewer than three gates per entry.
* levels select rails in input order; a search over selector orders saved
  7.95-9.86% of area at n=7 (200 tables, widths 40..200) and was retired.

**Constant tables need no muxes.**  Both are a single self-fed ``x`` or ``X``
gate, the shape the wiki's own constant-output circuit uses.

**Every wiring is driven exactly once.**  A ``:`` prints in *every*
generation its wire carries a value, and a wiring driven twice takes the
XOR of its drivers, so a second driver would corrupt both the value and the
output length.  Each bus here is written by exactly one gate (or one input
port) and only ever read after that, which is why the tests can assert that
a run prints exactly one character.
"""

from collections.abc import Iterator
from typing import Any, Literal

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language
from esolangs.tools.circuit_diagram.hlayout import _h_minterm_sites, _h_term_layout
from esolangs.tools.circuit_diagram.layout import _Layout
from esolangs.tools.helpers import (
    _validate_truth_table,
    essential_inputs,
    grid_width,
    narrowest_grid,
    read_at,
)

# Gate characters used by muxes and the two self-fed constant forms.
_GateGlyph = Literal["a", "o", "x", "X"]
_ConstGlyph = Literal["x", "X"]

__all__ = ["circuit_diagram"]

# Spacing.  Buses are two columns apart and gate bands two rows apart, so
# that no two junctions of different signals ever land within one cell of
# each other (see the module docstring's note on the eight-way ``.``).
_COL_STEP = 2
_ROW_STEP = 2


class _Builder:
    """Allocates buses and gate bands, and records their wiring.

    A *bus* is a vertical column carrying one signal, written once and read
    by any number of gates.  A gate occupies a three-row band and leaves its
    result on a fresh bus.
    """

    def __init__(self, *, narrow: bool = False) -> None:
        """Start an empty build."""
        # Input junction, gate, output junction, then one clear column:
        # different signals' junctions must remain two cells apart.
        self.gate_stride = 4 if narrow else 3 * _COL_STEP
        self.layout = _Layout()
        self.next_column = 1
        self.next_row = 0
        self.next_signal = 0
        # signal id -> (column, topmost row the bus has reached)
        self.buses: dict[int, tuple[int, int]] = {}
        # Gate column groups that may be handed out again, and the group each
        # recyclable signal was cut from.  Only a *gate's* output is ever
        # entered here: selector rails are shared, while every mux result is
        # read once by the carry that consumes it and then dies.
        self.free_strides: list[int] = []
        self.stride_of: dict[int, int] = {}
        # Set once a width is asked for: the column a new band starts at, and
        # the width the bands stay inside.  ``live`` is every intermediate
        # signal not yet read by its consumer, in creation order -- what a
        # band carries.  Rails and complements are never reclaimed.
        self.limit: int | None = None
        self.next_limit: int | None = None
        self.band_start = 0
        self.live: list[int] = []
        # Reads a shared gate output still awaits; it is released on the last.
        self.pending: dict[int, int] = {}

    def _new_signal(self) -> int:
        """Return a fresh signal id."""
        signal = self.next_signal
        self.next_signal += 1
        return signal

    def _new_column(self) -> int:
        """Return a fresh bus column, right of every bus column in use.

        Input rails only.  A rail is read by every mux level that selects it,
        so it is live for the whole drawing and its column is never given
        back; :func:`_gate_columns` is where the recycling happens.
        """
        column = self.next_column
        self.next_column += _COL_STEP
        return column

    def _gate_columns(self, after: int = -1) -> tuple[int, int]:
        """Reserve the columns one gate needs: its inputs, glyph, and output.

        Three consecutive columns are taken at once -- the input junctions,
        the gate itself, and the bus it drives -- so no earlier bus can run
        down through any of them: one through the input junction would make
        a single wiring of the gate's input and output, which the interpreter
        rejects.
        """
        # A dead group is reused, which is safe two ways.  Rows: the drawing
        # only moves *down* (``_new_band`` hands out increasing rows, ``_tap``
        # extends buses downward), so a recycled group's old wiring ends above
        # whatever is drawn into it.  Columns: a gate must sit *right* of every
        # bus it reads (``after`` is the rightmost), or the tap would cross the
        # gate's own glyph (:class:`_Layout` refuses it).
        usable = [group for group in self.free_strides if group + _COL_STEP > after]
        if usable:
            first = min(usable)
            self.free_strides.remove(first)
        else:
            first = self.next_column
            self.next_column += self.gate_stride
        return first, first + _COL_STEP

    def _band(self) -> None:
        """Start a fresh band of columns, carrying the live signals back left.

        Gates march right because one has to sit right of every bus it
        reads, so a column group freed behind the drawing can never be
        handed out again -- which is what makes the width grow with the
        network's depth.  A band breaks that: every signal still live is
        *moved* to a column near the left, and the columns behind it all
        become free again.

        Moving a bus needs no new primitive: :meth:`_tap` runs it down and
        then left, one wiring with one driver, crossing the rails with ``=``.
        Each carried signal takes its own row, since two signals' horizontal
        runs on one row would collide.

        Resetting the column counter is safe for the reason group reuse is:
        the drawing only ever moves down, so a column re-used in this band
        is entered below everything the last band left in it.
        """
        for offset, signal in enumerate(self.live):
            column = self.band_start + offset * _COL_STEP
            row = self._new_band()
            self._tap(signal, column, row)
            self.buses[signal] = (column, row)
        # A carried signal owns a column, not a gate group, so releasing it
        # gives nothing back.  It stays in ``live``: a later band must carry
        # it again, or that band hands its column to another signal.
        self.stride_of.clear()
        self.free_strides.clear()
        self.next_column = self.band_start + len(self.live) * _COL_STEP

    def _room(self, after: int) -> bool:
        """Whether a gate reading up to ``after`` fits without a new band."""
        if self.limit is None:
            return True
        if any(group + _COL_STEP > after for group in self.free_strides):
            return True
        boundary = self.next_column + self.gate_stride
        if boundary > self.limit:
            self.next_limit = (
                boundary if self.next_limit is None else min(self.next_limit, boundary)
            )
            return False
        return True

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
        if signal in self.live:
            self.live.remove(signal)

    def _read(self, signal: int) -> None:
        """Count one read of ``signal``, releasing it after its last."""
        left = self.pending.get(signal)
        if left is None or left <= 1:
            self.pending.pop(signal, None)
            self._release(signal)
        else:
            self.pending[signal] = left - 1

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

        One bus column is enough: an input port has no glyph, no inputs and
        no output column, and a gate's three columns left two empty columns
        per input for every later wire to cross.
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
        """Return a signal carrying ``~source``, computed once.

        Bands the same way :meth:`gate` does.  The complements are built
        before a limit is set, so this only ever fires for the ``~`` that
        inverts a dense table's result -- which is one gate past the whole
        network and was exactly the one that ran over the width.
        """
        if not self._room(self.buses[source][0]):
            self._band()
        _, column = self._gate_columns(self.buses[source][0])
        row = self._new_band()

        # ``~`` reads the cell level with it, so the tap has to end on the
        # junction immediately to its left rather than short of it.
        self._tap(source, column - 1, row)
        self.layout.glyph(column, row, "~")

        return self._drive(column + 1, row)

    def gate(self, kind: _GateGlyph, left: int, right: int) -> int:
        """Place a two-input ``kind`` gate and return its output signal.

        The group is taken before the inputs are read and the inputs are
        released after, so a gate can never be handed the very group it is
        about to read out of.

        When a width was asked for and this gate would take the drawing past
        it, :meth:`_band` carries the live signals back to the left first --
        so the check happens here, before the group is chosen, and the
        inputs' columns are re-read afterwards because the band has moved
        them.
        """
        if not self._room(max(self.buses[left][0], self.buses[right][0])):
            self._band()
        first, column = self._gate_columns(
            max(self.buses[left][0], self.buses[right][0])
        )
        row = self._new_band()

        self._tap(left, column - 1, row - 1)
        self._tap(right, column - 1, row + 1)
        self.layout.glyph(column, row, kind)

        signal = self._drive(column + 1, row)
        self.stride_of[signal] = first
        if self.limit is not None:
            self.live.append(signal)
        self._read(left)
        self._read(right)
        return signal

    def constant(self, source: int, kind: _ConstGlyph) -> int:
        """Return a constant signal, from one bus fed to both gate inputs.

        ``x`` of a value with itself is always 0 and ``X`` always 1, so a
        constant table needs no muxes.  Both of the gate's inputs come
        from the same bus, which the interpreter accepts because the wiki's
        own constant-output circuit is drawn that way.
        """
        _, column = self._gate_columns(self.buses[source][0])
        row = self._new_band()

        self._tap(source, column - 1, row - 1)
        self.layout.run_vertical(column - 1, row - 1, row + 1, source)
        self.layout.junction(column - 1, row + 1, source)
        self.layout.glyph(column, row, kind)

        return self._drive(column + 1, row)

    def _drive(self, column: int, row: int) -> int:
        """Return a fresh signal driven from a junction at ``(column, row)``."""
        signal = self._new_signal()
        self.layout.junction(column, row, signal)
        self.buses[signal] = (column, row)
        return signal

    def output(self, source: int) -> None:
        """Draw the ``:`` that prints ``source``'s value.

        ``:`` reads only a ``-`` directly to its left, so the signal is
        handed one cell along from the junction its bus already ends on.

        No band or gate columns are reserved: the bus it reads is the last
        one built, so its row is free to the right.  A fresh band put the
        output three rows below its gate -- the staircase small circuits
        used to end on.
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
        # A leg is skipped when the bus already sits on the tap's row or
        # column; the layout never produces that, but a head-on tap would
        # otherwise draw a zero-length run and a junction on top of the bus.
        if y != reached:  # pragma: no branch - a tap is never on the bus row
            self.layout.run_vertical(column, reached, y, signal)
            self.layout.junction(column, y, signal)
            self.buses[signal] = (column, y)
        if x != column:  # pragma: no branch - nor in the bus column
            self.layout.run_horizontal(column, x, y, signal)
            self.layout.junction(x, y, signal)


_Value = int | Literal["0", "1"]


def _mux(
    builder: _Builder, selectors: list[int | None], zero: _Value, one: _Value
) -> _Value:
    """Return ``zero`` or ``one`` according to ``selector``.

    ``(~selector AND zero) OR (selector AND one)`` is a three-gate mux.
    The caller shares each selector's complement across its whole level.
    """
    if zero == one:
        return zero
    selector = selectors[0]
    if selector is None:  # pragma: no cover - every selector has a plain rail
        raise AssertionError("selector has no plain rail")
    if zero == "0" and one == "1":
        return selector
    # The plain rail's two rules come first: a level that only ever takes
    # them has no complement to read (see :func:`_complemented_levels`).
    if zero == "0":
        if not isinstance(one, int):  # pragma: no cover - constants handled above
            raise AssertionError("unexpected constant mux arm")
        return builder.gate("a", selector, one)
    if one == "1":
        if not isinstance(zero, int):  # pragma: no cover - constants handled above
            raise AssertionError("unexpected constant mux arm")
        return builder.gate("o", selector, zero)
    negated = selectors[1]
    if negated is None:  # pragma: no cover - built before the fold
        raise AssertionError("selector has no complemented rail")
    if zero == "1" and one == "0":
        return negated
    if one == "0":
        if not isinstance(zero, int):  # pragma: no cover - constants handled above
            raise AssertionError("unexpected constant mux arm")
        return builder.gate("a", negated, zero)
    if zero == "1":
        if not isinstance(one, int):  # pragma: no cover - constants handled above
            raise AssertionError("unexpected constant mux arm")
        return builder.gate("o", negated, one)
    off = builder.gate("a", negated, zero)
    on = builder.gate("a", selector, one)
    return builder.gate("o", off, on)


_Dag = tuple[list[tuple[int, int, int, int]], int, set[int], dict[int, int]]


def _dag(truth_table: str, n: int) -> _Dag:
    """Return the fold as a shared DAG: ``(ops, root, needed, reads)``.

    ``ops`` lists each distinct mux ``(level, zero, one, node)`` once, in
    fold order; ids ``0``/``1`` are the constants.  Equal subtables are the
    same ``(level, zero, one)`` key, so a repeated subtree is built once and
    its signal read by every parent.  ``needed`` is the selector levels whose
    rule reads ``~selector``; ``reads`` is how many gates read each node.
    """
    stack: list[tuple[int, int]] = []
    nodes: dict[tuple[int, int, int], int] = {}
    ops: list[tuple[int, int, int, int]] = []
    needed: set[int] = set()
    reads: dict[int, int] = {}
    for bit in truth_table:
        identity, level = int(bit), 0
        while stack and stack[-1][1] == level:
            zero, _ = stack.pop()
            if zero != identity:
                key = (level, zero, identity)
                if key not in nodes:
                    nodes[key] = len(nodes) + 2
                    ops.append((level, zero, identity, nodes[key]))
                    # ``0/x`` is ``selector AND x`` and ``x/1`` is ``selector
                    # OR x``: only the plain rail is read, as for ``0/1``.
                    if zero != 0 and identity != 1:
                        needed.add(n - 1 - level)
                    for child in (zero, identity):
                        if child > 1:
                            reads[child] = reads.get(child, 0) + 1
                identity = nodes[key]
            level += 1
        stack.append((identity, level))
    [(root, level)] = stack
    if level != n:  # pragma: no cover - validation guarantees 2**n entries
        raise AssertionError("incomplete Shannon fold")
    return ops, root, needed, reads


def _shannon_fold(
    builder: _Builder, selectors: list[list[int | None]], dag: _Dag
) -> _Value:
    """Build each distinct mux of the DAG once; return the root's value."""
    ops, root, _, reads = dag
    n = len(selectors)
    values: dict[int, _Value] = {0: "0", 1: "1"}
    for level, zero, one, node in ops:
        signal = _mux(builder, selectors[n - 1 - level], values[zero], values[one])
        values[node] = signal
        if isinstance(signal, int) and signal in builder.stride_of:
            builder.pending[signal] = reads.get(node, 0)
    return values[root]


def _essential_table(truth_table: str, n: int) -> tuple[list[int], str]:
    """Return the essential inputs (input 0 for a constant) and the table over them."""
    used = essential_inputs(truth_table, n) or [0]
    return used, truth_table if len(used) == n else read_at(truth_table, used, n)


def _circuit_diagram_at(
    truth_table: str,
    limit: int | None,
    *,
    _events: list[int] | None = None,
) -> str:
    """Render the folded circuit inside an optional gate-column limit."""
    return _circuit_diagram_model(truth_table, limit, _events=_events).render()


def _circuit_diagram_model(
    truth_table: str,
    limit: int | None,
    *,
    _events: list[int] | None = None,
) -> _Layout:
    """Build a Circuit Diagram program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The table is folded bottom-up by Shannon expansion (:func:`_mux`): equal
    pairs share their signal, unequal pairs take at most three gates, and
    equal subtables are one node (:func:`_dag`), so construction is O(T)
    gates.

    Width is gate column groups, and a group is reused once its bus is dead.
    Only selector rails are read more than once; each mux result is read once
    by the carry above it.  A gate must sit right of every bus it reads, so
    the leftmost dead group past those buses is the one reused.

    The input rows are drawn first and in input order.
    """
    _validate_truth_table(truth_table)

    builder = _Builder(narrow=limit is not None)
    n = len(truth_table).bit_length() - 1
    # Every input keeps its ``-`` row (the read order), but the fold uses
    # only the essential inputs' rails; an ignored rail drives nothing, as
    # every rail but the first does for a constant table.
    used, table = _essential_table(truth_table, n)
    rails = [builder.input_bus() for _ in range(n)]
    if len(used) < n:
        rails = [rails[i] for i in used]
        truth_table = table
        n = len(used)

    dag = _dag(truth_table, n)
    complemented = dag[2]
    selectors: list[list[int | None]] = [
        [rail, builder.invert(rail) if level in complemented else None]
        for level, rail in enumerate(rails)
    ]
    builder.band_start = builder.next_column
    builder.limit = limit

    result = _shannon_fold(builder, selectors, dag)
    if result == "0":
        result = builder.constant(rails[0], "x")
    elif result == "1":
        result = builder.constant(rails[0], "X")
    builder.output(result)
    if _events is not None and builder.next_limit is not None:
        _events.append(builder.next_limit)
    return builder.layout


def _linear_shared_layout(table: str, inputs: int) -> _Layout | None:
    """Admit the folded model only within the H-layout's linear work and area."""
    used, projected = _essential_table(table, inputs)
    ops = _dag(projected, len(used))[0]
    # At most three gates per node, with O(nodes**2) interval insertion
    # and column scans. At most twice sqrt(T) nodes keeps that work O(T).
    if len(ops) ** 2 > 4 * len(table):
        return None
    sites = [
        point
        for prefix, point in _h_minterm_sites(inputs).items()
        if prefix.bit_length() - 1 >= 2
    ]
    floor = (max(x for x, _ in sites) - min(x for x, _ in sites) + 1) * (
        max(y for _, y in sites) - min(y for _, y in sites) + 1
    )
    # Every H build contains these minterm sites, so their box is an O(T)
    # area budget independent of density and the chosen candidate.
    model = _circuit_diagram_model(table, None)
    height, width = model.bounds()
    return model if height * width <= floor else None


def _affine_circuit(
    table: str, width: int, *, _events: list[int] | None = None
) -> str | None:
    from esolangs.tools.circuit_diagram.balance import affine_circuit

    return affine_circuit(table, width, _events=_events)


def _narrowest_present(*forms: str | None) -> str:
    """Return the narrowest grid among the forms that exist."""
    return narrowest_grid(*(form for form in forms if form is not None))


def circuit_diagram(truth_table: str, width: int | None = None) -> str:
    """Build a Circuit Diagram program computing the given truth table.

    See :func:`_circuit_diagram_at` for the construction.  ``width`` asks
    for a column count: the drawing is built once without one, and again
    inside the width if that came out too wide.

    From eight inputs an unconstrained nonconstant build tries a shared fold
    within linear work and area budgets, then the projected H-layout.

    What a width buys is *banding* (:meth:`_Builder._band`).  A mux layout's
    floor is what a band cannot reclaim -- the rails and complements, live
    for the whole drawing -- plus the carried signals and one gate group:
    about ``8 * n`` columns, growing with the inputs rather than the table.
    Below that floor, affine tables use native XOR/XNOR chains.
    """
    _validate_truth_table(truth_table)
    inputs = len(truth_table).bit_length() - 1
    # Constants need only the scalar clock gate, not a minterm lattice.
    if width is None and inputs >= 8 and "1" in truth_table and "0" in truth_table:
        shared = _linear_shared_layout(truth_table, inputs)
        if shared is not None:
            return shared.render()
        used, projected = _essential_table(truth_table, inputs)
        if len(used) < inputs:
            return _h_term_layout(
                projected, input_order=used, port_inputs=inputs
            ).render()
        return _h_term_layout(truth_table).render()
    flat = _circuit_diagram_at(truth_table, None)
    if width is None or grid_width(flat) <= width:
        return flat
    banded = _circuit_diagram_at(truth_table, width)
    if grid_width(banded) <= width:
        return banded
    # The output dash and colon extend beyond the final gate group.
    banded = _circuit_diagram_at(truth_table, max(1, width - 2))
    affine = _affine_circuit(truth_table, width)
    return _narrowest_present(flat, banded, affine)


def _balance(table: str, default: Any, **options: Any) -> Any:
    """Defer to the ``balance`` submodule, which imports this one."""
    from esolangs.tools.circuit_diagram.balance import (
        balance_circuit_diagram,  # circular
    )

    return balance_circuit_diagram(table, default, **options)


LANGUAGE = Language(
    "Circuit Diagram",
    "grid_based.circuit_diagram",
    layout_switch=(7, 8),
    example=Example(slow_build=True),
    # The H-layout is not asymptotic below n=8, so it has no room for a
    # third rung; the deep contract carries it on a backstop for the same
    # reason, and its area recurrence is checked with the construction
    # invariants.
    scaling_rungs=(8, 9),
    boolean=circuit_diagram,
    documented_sizes=(1_780_773, 2_505_897, 1.4),
    split=True,
    contract=BooleanContract(
        input_shape="char_stream",
        ignores_whitespace=True,
    ),
    balance=_balance,
    eof="resolves its inputs while laying the grid",
)
