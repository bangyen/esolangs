"""Circuit Diagram Boolean program generator: a mux fold over a wire model.

Each of ``n`` inputs arrives on its own line as a ``-`` input port (not one
``-n-`` multi-wire, which would need a ``<`` splitter tree back to rails).
A left-to-right binary-carry fold combines adjacent cofactors: equal ones
share a signal, ``0/1`` is the selector itself, the rest use a one- or
three-gate mux rule.  The answer prints through ``:``.  A constant table is
one self-fed ``x`` or ``X`` gate, the wiki's constant-output shape.  A
(negated) projection is one direct wire instead: every port is drawn,
as each is read, but only the essential port's row runs on to the
``:``, through a ``~`` when negated.

Wires are a *model* of segments rendered to characters afterwards, not
painted in draw order.  Every signal owns a vertical bus column, every gate a
three-row band: a gate at ``(c, r)`` reads ``.`` cells at ``(c - 1, r - 1)``
and ``(c - 1, r + 1)`` and drives ``(c + 1, r)`` (the spec's AND sample).
Shared selectors make the network non-planar, so crossings are intended:
the spec's ``-=-`` carries a horizontal and a vertical wire independently
(horizontal alone ``-``, vertical ``|``, both ``=``, endpoint ``.``).  A
``.`` joins all eight neighbours, so diagonally adjacent junctions of
different signals would silently merge; the renderer checks that, and two
signals sharing a cell in one direction, and raises rather than emit a wrong
circuit.  A ``:`` prints in every generation its wire carries a value and a
wiring driven twice takes the XOR of its drivers, so each bus is written by
one gate or port and a run prints one character.

A repeated subtree is built once (:func:`_dag`, hash-consed on ``(level,
zero, one)``); a shared output keeps its column group until its last read.
At most one unfinished signal per input level is live.  Wide unconstrained
builds compare natural order and two transposes moving the last three/four
inputs first; physical ports retain read order.

Size:
    One pass over the table, fewer than three gates per entry; n=8 and:
    1,207 chars, n=10 parity: 37,788 chars, n=10 random 1847: 669,345 chars.

Decisions:
    Sharing repeated subtrees, area vs the unshared build, mean of 20 seeded
    tables at n=5 / 6 / 7: random 0.93 / 0.91 / 0.92; two random 8-row blocks
    tiled at random 0.83 / 0.48 / 0.35, four 0.84 / 0.62 / 0.47.
"""

from collections.abc import Iterator
from typing import Any, Literal, NamedTuple

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    grid_width,
    narrowest_grid,
    read_at,
)
from esolangs.languages.circuit_diagram.generator.columns import _FreeColumns
from esolangs.languages.circuit_diagram.generator.layout import (
    _Layout,
    _resolve_order,
)
from esolangs.languages.circuit_diagram.proof_formulas import workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

# Gate characters used by muxes and the two self-fed constant forms.
_GateGlyph = Literal["a", "o", "x", "X"]
_ConstGlyph = Literal["x", "X"]

__all__ = ["circuit_diagram"]

# Spacing.  Buses are two columns apart and gate bands two rows apart, so
# that no two junctions of different signals ever land within one cell of
# each other (see the module docstring's note on the eight-way ``.``).
_COL_STEP = 2
_ROW_STEP = 2

# Layout competition starts at four inputs: it never grows a table there
# ([ablations.competing_model_floor]), and it wins no n <= 3 table, where it
# would only slow generation.
_COMPETING_MODEL_MIN_INPUTS = 4
# Columns the output dash and colon add past the final gate group, so
# banding rebuilds this much narrower when the first attempt is too wide.
_OUTPUT_GLYPH_COLUMNS = 2


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
        # Width banding: the width bands stay inside, once asked for, and the
        # column a new band starts at.
        self.limit: int | None = None
        self.band_start = 0
        # Unread intermediate signals, in creation order: what a band carries.
        self.live: list[int] = []
        # Reads a shared gate output still awaits; it is released on the last.
        self.pending: dict[int, int] = {}
        # Recyclable column groups.  Only a *gate's* output enters here:
        # rails are shared, and a mux result dies at its one read.
        self.stride_of: dict[int, int] = {}
        self.free_strides = _FreeColumns()

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
        first = self.free_strides.take_after(after - _COL_STEP)
        if first is None:
            first = self.next_column
            self.next_column += self.gate_stride
        return first, first + _COL_STEP

    def _band(self) -> None:
        """Start a fresh band of columns, carrying the live signals back left.

        A gate must sit right of every bus it reads, so a group freed behind
        the drawing can never be handed out again, and width grows with the
        network's depth.  A band *moves* every live signal to a column near
        the left and frees all the columns behind it.  A mux layout's floor
        is what a band cannot reclaim -- the rails and complements, live for
        the whole drawing -- plus the carried signals and one gate group:
        about ``8 * n`` columns, growing with the inputs rather than the table.

        :meth:`_tap` does the move (down then left, one wiring with one
        driver, crossing the rails with ``=``).  Each carried signal takes
        its own row, since two horizontal runs on one row would collide.

        Resetting the column counter is safe as group reuse is: the drawing
        only moves down, so a re-used column is entered below everything the
        last band left in it.
        """
        self._carry_live_signals()
        self._reset_band_columns()

    def _carry_live_signals(self) -> None:
        """Move every live signal to its own column at the band's left."""
        for offset, signal in enumerate(self.live):
            column = self.band_start + offset * _COL_STEP
            row = self._new_band()
            self._tap(signal, column, row)
            self.buses[signal] = (column, row)

    def _reset_band_columns(self) -> None:
        """Free every column behind the band and restart allocation left."""
        # A carried signal owns a column, not a gate group, so releasing it
        # gives nothing back.  It stays in ``live``: a later band must carry
        # it again, or that band hands its column to another signal.
        self.stride_of.clear()
        self.free_strides.clear()
        self.next_column = self.band_start + len(self.live) * _COL_STEP

    def _gate_placement(self, *signals: int) -> tuple[int, int, int]:
        """Reserve a gate group and band row reading ``signals``.

        Past a requested width, :meth:`_band` carries the live signals left
        before the group is chosen, so the inputs' columns are re-read after
        it.  Returns ``(first column, gate column, band row)``.
        """
        after = max(self.buses[signal][0] for signal in signals)
        if not self._room(after):
            self._band()
            after = max(self.buses[signal][0] for signal in signals)
        first, column = self._gate_columns(after)
        return first, column, self._new_band()

    def _room(self, after: int) -> bool:
        """Whether a gate reading up to ``after`` fits without a new band."""
        if self.limit is None:
            return True
        if self.free_strides.first_after(after - _COL_STEP) is not None:
            return True
        return self.next_column + self.gate_stride <= self.limit

    def _release(self, signal: int) -> None:
        """Give back ``signal``'s column group, if it owns one to give.

        Called once the signal has been read into the gate that consumes
        it.  A rail or a complement is not in :attr:`stride_of` at all and
        so is never released; a gate output is removed as it is released, so
        a second call cannot hand the same group out twice.
        """
        stride = self.stride_of.pop(signal, None)
        if stride is not None:
            self.free_strides.add(stride)
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

        Each input owns a row, in the order the interpreter reads the bits.
        """
        # One bus column is enough: a port has no glyph, inputs or output
        # column, and a gate's three columns left two empty columns per input
        # for later wires to cross.
        signal = self._new_signal()
        column = self._new_column()
        row = self.next_row
        self.next_row += _ROW_STEP

        self.layout.input_port(row, column, signal)
        self.buses[signal] = (column, row)
        return signal

    def selectors(
        self, rails: list[int], complemented: set[int]
    ) -> list[list[int | None]]:
        """Return ``[rail, ~rail]`` per level, the complement only where read."""
        return [
            [rail, self.invert(rail) if level in complemented else None]
            for level, rail in enumerate(rails)
        ]

    def invert(self, source: int) -> int:
        """Return a signal carrying ``~source``, computed once.

        Bands the same way :meth:`gate` does.  The complements are built
        before a limit is set, so this only ever fires for the ``~`` that
        inverts a dense table's result -- which is one gate past the whole
        network and was exactly the one that ran over the width.
        """
        _, column, row = self._gate_placement(source)

        # ``~`` reads the cell level with it, so the tap has to end on the
        # junction immediately to its left rather than short of it.
        self._tap(source, column - 1, row)
        self.layout.glyph(column, row, "~")

        return self._drive(column + 1, row)

    def gate(self, kind: _GateGlyph, left: int, right: int) -> int:
        """Place a two-input ``kind`` gate and return its output signal.

        The group is taken before the inputs are read and they are released
        after, so a gate is never handed the group it reads out of.
        """
        first, column, row = self._gate_placement(left, right)

        self._tap(left, column - 1, row - 1)
        self._tap(right, column - 1, row + 1)
        self.layout.glyph(column, row, kind)

        return self._drive_gate_output(column, row, first, left, right)

    def _drive_gate_output(
        self, column: int, row: int, first: int, left: int, right: int
    ) -> int:
        """Drive a placed gate's output bus, then release its two inputs."""
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

        ``:`` reads only a ``-`` directly to its left, so the signal moves one
        cell along from the junction its bus ends on.
        """
        # No band is reserved: the bus is the last one built, so its row is
        # free to the right; a fresh band would stair-step small circuits.
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


def _signal(arm: _Value) -> int:
    """Narrow a mux arm the constant cases have already ruled out."""
    if not isinstance(arm, int):  # pragma: no cover - constants handled above
        raise AssertionError("unexpected constant mux arm")
    return arm


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
        return builder.gate("a", selector, _signal(one))
    if one == "1":
        return builder.gate("o", selector, _signal(zero))
    negated = selectors[1]
    if negated is None:  # pragma: no cover - built before the fold
        raise AssertionError("selector has no complemented rail")
    if zero == "1" and one == "0":
        return negated
    if one == "0":
        return builder.gate("a", negated, _signal(zero))
    if zero == "1":
        return builder.gate("o", negated, _signal(one))
    return _three_gate_mux(builder, selector, negated, zero, one)


def _three_gate_mux(
    builder: _Builder, selector: int, negated: int, zero: int, one: int
) -> int:
    """Return the full mux: ``(~selector AND zero) OR (selector AND one)``."""
    off = builder.gate("a", negated, zero)
    on = builder.gate("a", selector, one)
    return builder.gate("o", off, on)


class _Dag(NamedTuple):
    """A shared Shannon-fold DAG; see :func:`_dag`."""

    ops: list[tuple[int, int, int, int]]
    root: int
    needed: set[int]
    reads: dict[int, int]


def _note_mux(
    needed: set[int], reads: dict[int, int], selector: int, zero: int, one: int
) -> None:
    """Record a new ``zero/one`` mux on ``selector``'s rail.

    ``0/x`` is ``selector AND x`` and ``x/1`` is ``selector OR x``: only the
    plain rail is read, as for ``0/1``; any other mux needs ``~selector``.
    """
    if zero != 0 and one != 1:
        needed.add(selector)
    for child in (zero, one):
        if child > 1:
            reads[child] = reads.get(child, 0) + 1


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
                    _note_mux(needed, reads, n - 1 - level, zero, identity)
                identity = nodes[key]
            level += 1
        stack.append((identity, level))
    [(root, level)] = stack
    if level != n:  # pragma: no cover - validation guarantees 2**n entries
        raise AssertionError("incomplete Shannon fold")
    return _Dag(ops, root, needed, reads)


def _emit_dag(
    builder: _Builder, selectors: list[list[int | None]], dag: _Dag
) -> dict[int, _Value]:
    """Emit shared muxes and retain their values for single or multiple roots."""
    n = len(selectors)
    values: dict[int, _Value] = {0: "0", 1: "1"}
    for level, zero, one, node in dag.ops:
        signal = _mux(builder, selectors[n - 1 - level], values[zero], values[one])
        values[node] = signal
        if isinstance(signal, int) and signal in builder.stride_of:
            builder.pending[signal] = dag.reads.get(node, 0)
    return values


def _finish_fold(
    builder: _Builder, selectors: list[list[int | None]], dag: _Dag
) -> _Layout:
    """Emit one root, using a self-fed gate for either constant."""
    result = _emit_dag(builder, selectors, dag)[dag.root]
    if isinstance(result, str):
        rail = selectors[0][0]
        if rail is None:  # pragma: no cover - every selector has a plain rail
            raise AssertionError("selector has no plain rail")
        result = builder.constant(rail, "x" if result == "0" else "X")
    builder.output(result)
    return builder.layout


def _essential_table(truth_table: str, n: int) -> tuple[list[int], str]:
    """Return the essential inputs (input 0 for a constant) and the table over them."""
    used = essential_inputs(truth_table, n) or [0]
    return used, truth_table if len(used) == n else read_at(truth_table, used, n)


def _projection_wire(truth_table: str, inputs: int) -> str | None:
    """Return the direct wire for a (negated) projection, else ``None``.

    Every port is still drawn -- each is read, so a run still consumes
    the shipped ``inputs`` bits -- but only the essential port's row
    runs on: ``-:`` for a projection, ``-~-:`` for a negated one.  The
    port grid costs n^2 + 3n characters for a projection (88 at n = 8)
    and 130..162 for a negated one; the wire costs 2n, or 2n + 2
    negated (16 and 18 at n = 8).
    """
    used, reduced = _essential_table(truth_table, inputs)
    if len(used) != 1 or reduced not in ("01", "10"):
        return None
    wire = "-:" if reduced == "01" else "-~-:"
    return "\n".join(wire if level == used[0] else "-" for level in range(inputs))


def _circuit_diagram_at(truth_table: str, limit: int | None) -> str:
    """Render the folded circuit inside an optional gate-column limit."""
    return _circuit_diagram_model(truth_table, limit).render()


def _circuit_diagram_model(
    truth_table: str,
    limit: int | None,
    *,
    input_order: list[int] | None = None,
    port_inputs: int | None = None,
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
    order, port_inputs = _resolve_order(input_order, n, port_inputs, "fold")
    # Every input keeps its ``-`` row (the read order), but the fold uses
    # only the essential inputs' rails; an ignored rail drives nothing, as
    # every rail but the first does for a constant table.
    used, table = _essential_table(truth_table, n)
    ports = [builder.input_bus() for _ in range(port_inputs)]
    rails = [ports[order[i]] for i in used]

    dag = _dag(table, len(used))
    selectors = builder.selectors(rails, dag.needed)
    builder.band_start = builder.next_column
    builder.limit = limit

    _finish_fold(builder, selectors, dag)
    return builder.layout


def _linear_shared_layout(table: str, inputs: int, models: list[_Layout]) -> None:
    """Append the complete fixed-order folds to ``models`` for the race."""
    used, projected = _essential_table(table, inputs)
    candidates = [(projected, used)]
    for tail in (3, 4):
        if len(used) > tail:
            # A fixed block transpose moves the last inputs first in O(T),
            # without changing port reads or searching selector orders.
            rotated = "".join(projected[i :: 1 << tail] for i in range(1 << tail))
            candidates.append((rotated, used[-tail:] + used[:-tail]))
    for candidate, order in candidates:
        models.append(
            _circuit_diagram_model(
                candidate, None, input_order=order, port_inputs=inputs
            )
        )


def _narrowest_present(*forms: str | None) -> str:
    """Return the narrowest grid among the forms that exist."""
    return narrowest_grid(*(form for form in forms if form is not None))


def _competing_model_circuit(truth_table: str, inputs: int) -> str:
    """Return the smallest emitted-character circuit among the n>=4 layouts.

    Three complete fixed-order folds compete by area against prefix
    H-layouts and shared class banks; sharing wins character ties.
    """
    from .compete import select_competing_model  # cycle: candidates import this module
    from .source_size import layout_source_size

    retained: list[_Layout] = []
    _linear_shared_layout(truth_table, inputs, retained)
    selected = select_competing_model(truth_table, inputs)
    # Text contracts count characters; a taller area winner can lose.
    fallback = selected
    code = fallback.render()
    size = len(code)
    for model in retained:
        model_size = layout_source_size(model)
        if model_size < size or (model_size == size and selected not in retained):
            selected, size = model, model_size
    return code if selected is fallback else selected.render()


def circuit_diagram(truth_table: str, width: int | None = None) -> str:
    """Build a Circuit Diagram program computing the given truth table.

    See :func:`_circuit_diagram_model` for the construction.  ``width`` asks
    for a column count: built once without one, again inside it if too wide
    (:meth:`_Builder._band`); below the banding floor, affine tables use
    native XOR/XNOR chains.
    """
    _validate_truth_table(truth_table)
    inputs = len(truth_table).bit_length() - 1
    # A (negated) projection is one direct wire, not the whole port grid;
    # below the wire's own width the fitted builds below decide as before.
    wire = _projection_wire(truth_table, inputs)
    if wire is not None and (width is None or grid_width(wire) <= width):
        return wire
    # Constants need only the scalar clock gate, not a minterm lattice.
    if (
        width is None
        and inputs >= _COMPETING_MODEL_MIN_INPUTS
        and "1" in truth_table
        and "0" in truth_table
    ):
        return _competing_model_circuit(truth_table, inputs)
    flat = _circuit_diagram_at(truth_table, None)
    if width is None or grid_width(flat) <= width:
        return flat
    banded = _circuit_diagram_at(truth_table, width)
    if grid_width(banded) <= width:
        return banded
    # The output dash and colon extend beyond the final gate group.
    banded = _circuit_diagram_at(truth_table, max(1, width - _OUTPUT_GLYPH_COLUMNS))
    from esolangs.languages.circuit_diagram.generator.balance import (
        affine_circuit,  # circular
    )

    affine = affine_circuit(truth_table, width)
    return _narrowest_present(flat, banded, affine)


def _balance(table: str, default: Any, **options: Any) -> Any:
    """Defer to the ``balance`` submodule, which imports this one."""
    from esolangs.languages.circuit_diagram.generator.balance import (
        balance_circuit_diagram,  # circular
    )

    return balance_circuit_diagram(table, default, **options)


LANGUAGE = Language(
    "Circuit Diagram",
    "circuit_diagram",
    category="grid_based",
    layout_switch=(7, 8),
    example=Example(slow_build=True),
    # The H-layout is not asymptotic below n=8, so it has no room for a
    # third rung; the deep contract carries it on a backstop for the same
    # reason, and its area recurrence is checked with the construction
    # invariants.
    scaling_rungs=(8, 9),
    boolean=circuit_diagram,
    documented_sizes=(128_824, 258_216, 2.0),
    split=True,
    contract=BooleanContract(
        input_shape="char_stream",
        ignores_whitespace=True,
    ),
    balance=_balance,
    eof="resolves its inputs while laying the grid",
    proof_workspace=(workspace, False, (3, 6)),
)
