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
* each input and any complement the mux rules need is built once and shared;
* a left-to-right binary-carry fold combines adjacent cofactors.  Equal
  cofactors share one signal, ``0/1`` is the selector itself, and the other
  cases use a fixed one- or three-gate mux rule;
* at most one unfinished signal per input level is live; the fold is one
  pass over the table and emits fewer than three gates per entry.
* through seven inputs the fold is built for up to four *selector orders*
  and the shortest drawing ships.  The rails keep their rows and read order;
  only which rail each Shannon level selects moves, which is the table's
  inputs renamed (:func:`_selector_orders`).

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
from typing import Literal

from esolangs.tools.circuit_diagram.hlayout import _h_term_layout
from esolangs.tools.circuit_diagram.layout import _Layout
from esolangs.tools.helpers import (
    _greedy_input_order,
    _validate_truth_table,
    essential_inputs,
    grid_width,
    narrowest_grid,
    permute_truth_table,
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

# The flat route's widest arity: from eight inputs an unconstrained build is
# the H-layout, which is not reordered.  Selector orders are only chosen up
# to here -- a width-bound build past it keeps the identity -- so their
# scoring is bounded work and the wide route's generation stays O(T).
_REORDER_MAX_ARITY = 7


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
        # Set once a width is asked for: the column a new band starts at,
        # and the width the bands have to stay inside.  ``live`` is every
        # intermediate signal not yet read into the gate that consumes it,
        # in the order they were made -- what a band has to carry.  Rails
        # and complements are not in it: they are read by everything, sit
        # left of ``band_start``, and are never reclaimed.
        self.limit: int | None = None
        self.next_limit: int | None = None
        self.band_start = 0
        self.live: list[int] = []

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
        # A dead group is reused rather than a fresh one taken.  Two things
        # make that safe.
        #
        # Rows: the drawing only ever moves *down*.  ``_new_band`` hands out
        # increasing rows and ``_tap`` only extends a bus downward, so a
        # recycled group's old wiring ends at the row of the gate that read
        # it last, and everything drawn into it afterwards starts a band
        # below that.
        #
        # Columns: a gate must sit *right* of every bus it reads.  ``_tap``
        # runs the bus along the gate's row to the input junction, so a group
        # left of a source would cross the gate's own glyph (:class:`_Layout`
        # refuses it).  ``after`` is the rightmost bus the gate will read.
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
        self._release(left)
        self._release(right)
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


def _shannon_fold(
    builder: _Builder,
    selectors: list[list[int | None]],
    truth_table: str,
) -> _Value:
    """Fold the table in one pass, keeping one partial signal per level."""
    stack: list[tuple[_Value, int]] = []
    n = len(selectors)
    for bit in truth_table:
        signal: _Value = "1" if bit == "1" else "0"
        level = 0
        while stack and stack[-1][1] == level:
            zero, _ = stack.pop()
            signal = _mux(builder, selectors[n - 1 - level], zero, signal)
            level += 1
        stack.append((signal, level))
    [(result, level)] = stack
    if level != n:  # pragma: no cover - validation guarantees 2**n entries
        raise AssertionError("incomplete Shannon fold")
    return result


def _complemented_levels(truth_table: str, n: int) -> set[int]:
    """Return selector levels whose direct mux rule needs ``~selector``.

    Identities have to compare the way :func:`_mux`'s signals do.  Only a
    constant or a level's own rail is ever the same signal twice; every gate
    output is fresh, so two cofactors that compute the same function from
    different gates are *unequal* to the fold and take a real mux; hashing
    them together skipped its complement, and twenty four-input tables
    (``0000111100010001`` first) raised.
    """
    stack: list[tuple[int, int]] = []
    rails: dict[tuple[int, int, int], int] = {}
    needed: set[int] = set()
    next_identity = 2
    for bit in truth_table:
        identity, level = int(bit), 0
        while stack and stack[-1][1] == level:
            zero, _ = stack.pop()
            if zero != identity:
                # ``0/x`` is ``selector AND x`` and ``x/1`` is ``selector OR
                # x``: only the plain rail is read, as for ``0/1`` itself.
                if zero != 0 and identity != 1:
                    needed.add(n - 1 - level)
                key = (level, zero, identity)
                if key in rails:
                    identity = rails[key]
                else:
                    if (zero, identity) in ((0, 1), (1, 0)):
                        rails[key] = next_identity
                    identity = next_identity
                    next_identity += 1
            level += 1
        stack.append((identity, level))
    return needed


# A fold token that is a gate's output.  Unlike a constant or a rail it is
# never the same signal twice, so two of them always take a real mux.
_GATE = -1


def _mux_cost(zero: int, one: int) -> tuple[int, bool]:
    """Return what :func:`_mux` spends on a pair: gates, and whether ``~``."""
    if zero == one and zero != _GATE:
        return 0, False
    if (zero, one) == (0, 1):
        return 0, False
    if (zero, one) == (1, 0):
        return 0, True
    if zero == 0 or one == 1:
        return 1, False
    if zero == 1 or one == 0:
        return 1, True
    return 3, True


def _pairs(tokens: list[int], stride: int) -> Iterator[tuple[int, int]]:
    """Yield each (zero, one) cofactor pair a level at ``stride`` muxes."""
    for block in range(0, len(tokens), 2 * stride):
        for x in range(block, block + stride):
            yield tokens[x], tokens[x + stride]


def _cheapest_selector_order(truth_table: str, n: int) -> tuple[int, ...]:
    """Pick each Shannon level's rail bottom-up by what its muxes cost.

    A level's cost is read straight off its pairs with :func:`_mux_cost`,
    one per gate plus one for a complement.  The pairs a level sees do not
    depend on the order *below* it -- a cofactor is a constant, a rail or a
    gate whichever way it was folded -- so the bottom level is chosen first,
    folded, and the next chosen over what is left.  Ties keep the identity's
    rail.  Each level scores every remaining input over the remaining
    table, so the whole choice is ``O(n * 2**n)``.
    """
    tokens = [int(bit) for bit in truth_table]
    remaining = list(range(n))
    bottom_up: list[int] = []
    while len(remaining) > 1:
        best_pos, best_cost = len(remaining) - 1, -1
        for pos in range(len(remaining) - 1, -1, -1):
            stride = 1 << (len(remaining) - 1 - pos)
            cost, complement = 0, False
            for zero, one in _pairs(tokens, stride):
                gates, negated = _mux_cost(zero, one)
                cost += gates
                complement = complement or negated
            cost += complement
            if best_cost < 0 or cost < best_cost:
                best_pos, best_cost = pos, cost
        stride = 1 << (len(remaining) - 1 - best_pos)
        rail = remaining.pop(best_pos)
        folded = []
        for zero, one in _pairs(tokens, stride):
            if zero == one and zero != _GATE:
                folded.append(zero)
            elif (zero, one) == (0, 1):
                folded.append(2 + 2 * rail)
            elif (zero, one) == (1, 0):
                folded.append(3 + 2 * rail)
            else:
                folded.append(_GATE)
        tokens = folded
        bottom_up.append(rail)
    return tuple(remaining + bottom_up[::-1])


def _essential_table(truth_table: str, n: int) -> tuple[list[int], str]:
    """Return the essential inputs (input 0 for a constant) and the table over them."""
    used = essential_inputs(truth_table, n) or [0]
    return used, truth_table if len(used) == n else read_at(truth_table, used, n)


def _selector_orders(
    truth_table: str, *, compact: bool = False
) -> list[tuple[int, ...] | None]:
    """Return named selector orders, identity first.

    Compact builds keep identity, mux-cost greedy and reverse. Width requests
    also try the constant-cofactor greedy order. Rails remain in input order.
    """
    n = len(truth_table).bit_length() - 1
    if n > _REORDER_MAX_ARITY:
        return [None]
    used, table = _essential_table(truth_table, n)
    identity = tuple(range(len(used)))
    orders: list[tuple[int, ...] | None] = [None]
    for order in (
        identity if compact else _greedy_input_order(table, len(used)),
        _cheapest_selector_order(table, len(used)),
        identity[::-1],
    ):
        if order != identity and order not in orders:
            orders.append(order)
    return orders


def _circuit_diagram_at(
    truth_table: str,
    limit: int | None,
    perm: tuple[int, ...] | None = None,
    *,
    _events: list[int] | None = None,
) -> str:
    """Build a Circuit Diagram program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The table is folded bottom-up by Shannon expansion (:func:`_mux`): equal
    pairs share their signal, unequal pairs take at most three gates, so
    construction is O(T) gates.

    Width is gate column groups, and a group is reused once its bus is dead.
    Only selector rails are read more than once; each mux result is read once
    by the carry above it.  A gate must sit right of every bus it reads, so
    the leftmost dead group past those buses is the one reused.

    ``perm`` renames the essential inputs' levels: level ``k`` selects rail
    ``perm[k]``.  The input rows are drawn first and in input order either
    way.
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
    if perm is not None:
        truth_table = permute_truth_table(truth_table, perm)
        rails = [rails[i] for i in perm]

    complemented = _complemented_levels(truth_table, n)
    selectors: list[list[int | None]] = [
        [rail, builder.invert(rail) if level in complemented else None]
        for level, rail in enumerate(rails)
    ]
    builder.band_start = builder.next_column
    builder.limit = limit

    result = _shannon_fold(builder, selectors, truth_table)
    if result == "0":
        result = builder.constant(rails[0], "x")
    elif result == "1":
        result = builder.constant(rails[0], "X")
    builder.output(result)
    if _events is not None and builder.next_limit is not None:
        _events.append(builder.next_limit)
    return builder.layout.render()


def _affine_circuit(
    table: str, width: int, *, _events: list[int] | None = None
) -> str | None:
    from esolangs.tools.circuit_diagram.balance import affine_circuit

    return affine_circuit(table, width, _events=_events)


def _flat_best(
    truth_table: str, *, compact: bool
) -> tuple[str, tuple[int, ...] | None]:
    """Return the shortest unbanded drawing and its selector order.

    ``min`` keeps the first on a tie, so the identity only gives way to a win.
    """
    return min(
        (
            (_circuit_diagram_at(truth_table, None, order), order)
            for order in _selector_orders(truth_table, compact=compact)
        ),
        key=lambda built: len(built[0]),
    )


def _narrowest_present(*forms: str | None) -> str:
    """Return the narrowest grid among the forms that exist."""
    return narrowest_grid(*(form for form in forms if form is not None))


def circuit_diagram(truth_table: str, width: int | None = None) -> str:
    """Build a Circuit Diagram program computing the given truth table.

    See :func:`_circuit_diagram_at` for the construction.  ``width`` asks
    for a column count: the drawing is built once without one, and again
    inside the width if that came out too wide.

    Below eight inputs the shortest named selector order is kept. Compact
    builds use three orders; width requests keep all four. Retiring the
    constant-cofactor greedy choice adds 3.29% to the three-input total
    and 1.62% to the seeded five-input sample.

    From eight inputs an unconstrained build uses the H-layout instead;
    :mod:`.hlayout` gives why, and why at eight.

    What a width buys is *banding* (:meth:`_Builder._band`).  A mux layout's
    floor is what a band cannot reclaim -- the rails and complements, live
    for the whole drawing -- plus the carried signals and one gate group:
    about ``8 * n`` columns, growing with the inputs rather than the table.
    Below that floor, affine tables use native XOR/XNOR chains.
    """
    _validate_truth_table(truth_table)
    inputs = len(truth_table).bit_length() - 1
    if width is None and inputs >= 8 and "1" in truth_table:
        return _h_term_layout(truth_table).render()
    flat, order = _flat_best(truth_table, compact=width is None)
    if width is None or grid_width(flat) <= width:
        return flat
    banded = _circuit_diagram_at(truth_table, width, order)
    if grid_width(banded) <= width:
        return banded
    # The output dash and colon extend beyond the final gate group.
    banded = _circuit_diagram_at(truth_table, max(1, width - 2), order)
    affine = _affine_circuit(truth_table, width)
    return _narrowest_present(flat, banded, affine)
