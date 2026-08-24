r"""Interpreter for Circuit Diagram.

An ASCII circuit diagram is executed the way the hardware it draws would
behave: wires drawn with ``-``, ``|``, ``/`` and ``\`` join named logic
gates, and the whole grid is evaluated as a cellular automaton in which a
gate drives its output wiring in the *next* generation, once it holds a
value for every input slot and one of them has just arrived (see the
judgment calls below, which derive that rule from the page's own flip-flop).
There is no instruction pointer -- every gate is live at once, which is what
separates this from every other grid language in the package.

The gates, tabulated by the wiki (https://esolangs.org/wiki/Circuit_Diagram):

=========  ================================================
``a``      AND -- 1 iff every input wire is 1
``A``      NAND -- 0 iff every input wire is 1
``o``      OR -- 1 iff any input wire is 1
``O``      NOR -- 1 iff no input wire is 1
``x``      XOR -- 1 iff exactly one input wire is 1
``X``      XNOR -- 1 iff all inputs are 0, or more than one is 1
``~``      NOT -- inverts each wire, returning as many as it took
=========  ================================================

Every gate but ``~`` takes two inputs from its left and drives one output
to its right; ``~`` takes one.  ``<`` splits a multi-wire in half and ``>``
appends its second input to its first.  ``-n-`` labels a wiring as carrying
``n`` wires, a leading ``-`` on a line reads that many bits of input, and
``:`` prints the wire directly to its left.

Wiring
------

A *wiring* is a group of wires connected directly or indirectly to each
other but not through a gate, and it holds one value: Null, 0, or 1 (a
tuple of those when it is a multi-wire).  Two wires are connected only when
they point at each other -- the spec's "for there to be a connection, a wire
must be connected both ways", which makes ``-|`` and even ``.|`` non-
connections.  ``.`` connects to all eight of its neighbours, and ``=`` is a
crossover: a wire entering one side continues out the opposite side without
joining what crosses it.  ``=`` chains, so the ``.===.`` on the prime
tester's tenth line joins its two ``.``s across three crossover cells; the
pass-through is therefore iterative rather than a single-cell hop.

Judgment calls
--------------

Four things a running interpreter must settle are unstated on the page.
Each is resolved below against the page's own worked example -- the 4-bit
prime tester, which the test suite replays over all sixteen inputs -- rather
than invented:

* **Values are events, and gates latch them.**  The page never says when
  ``:`` prints or when a program stops, and the obvious reading -- wirings
  hold their value until overwritten, run until nothing changes -- is
  *falsified by the page's own flip-flop*, which it says outputs
  ``1N1N1N...``: a sticky wiring can never show a Null after a 1.  So a
  wiring's value lasts one generation, being the XOR of whatever fired into
  it that generation and Null when nothing did.

  That alone would break the prime tester, whose final ``a`` is fed by two
  chains of different depths that would never be live together.  The spec
  covers this in the sentence "when one input has arrived, but the other
  has not, the gate waits until the other input comes": each gate keeps a
  **latch per input slot**, a non-null arrival fills or overwrites its slot
  ("the gate takes that into account"), and the gate fires when every slot
  is filled *and* at least one input is live this generation.  Requiring a
  live arrival is what stops a filled latch from re-firing forever, which
  is what lets the flip-flop alternate instead of pinning itself.

  ``:`` therefore prints whenever its wire carries a value, and a program
  halts on a quiescent generation -- nothing fired and every wiring Null.
  A feedback circuit never quiesces and is bounded instead by
  :func:`esolangs.vm.run_until_halt_or_cycle`, which proves the flip-flop's
  period-2 oscillation; the latches are part of :meth:`_Machine.snapshot`,
  since two generations with equal wiring values but different latches are
  not the same state.

* **Which input bit is which wire.**  ``-4-`` reads four bits, and the
  example's minterm formula is only primality when the first wire is the
  most significant bit (``a`` in the page's formula).  The other three
  orderings each yield a different, non-prime set, so the example pins its
  own bit ordering: **wire 1 is the first bit read and the MSB.**

* **Input format.**  The page never says how bits arrive.  One line per
  bit, taking ``1`` as a one bit and anything else as zero, is the
  convention the package's other bit-oriented grid language (Flowchart)
  already uses, so it is followed here rather than inventing a second.

* **Gate ports are direction-sets, not fixed cells.**  The AND sample draws
  its inputs on the upper- and lower-left diagonals, but the prime tester
  feeds the ``<`` at column 5 of its third line from the upper-left ``/``
  and the one on its seventh line from the lower-left ``\``, so an input is
  not always at a fixed offset.  A gate therefore accepts a connection from
  any of its three left-hand neighbours and drives any of its three
  right-hand ones, subject to the mutual-connection rule and to the spec's
  own constraint that **one wiring may not touch both a gate's inputs and
  its output** -- which is what disambiguates the junctions in the example
  where a single ``.`` sits diagonally adjacent to a gate it does not feed.

  Two gates narrow that further, each on the spec's own wording.  ``<``
  drives only its two right-hand diagonals ("any wire that connects to the
  ``<`` from the upper right or lower right receives the wire"), so the
  cell straight ahead of a splitter belongs to the wiring feeding it, which
  is exactly how the prime tester draws it.  ``~`` takes only the cell
  level with it (the sample is ``.~.``), so a diagonal neighbour is another
  wiring routed past the gate rather than a second input.  Conversely, one
  wiring may feed *both* slots of a two-input gate: the constant-output
  circuit runs a single wiring into both sides of its ``a``, so ports are
  counted per cell rather than per wiring.

The prime tester is drawn with two gaps
--------------------------------------

The page's only worked example, a 4-bit prime tester, is missing five
characters, and as drawn it prints nothing at all: two of its OR gates have
an input that no gate drives, so under the spec's own "gates wait" rule
they never fire and the circuit never reaches its output.
``tests/interpreters/test_circuit_diagram.py`` carries both forms --
``PRIME_TESTER``, the page's diagram plus those five characters, replayed
over all sixteen inputs, and ``PRIME_TESTER_AS_DRAWN``, whose silence is
pinned so a later change to the connection rules cannot quietly turn the
broken diagram into a working one.

The repair is *derived*, not guessed, and it is unique.  The circuit is not
the sum-of-minterms its caption implies but a product of sums: the final
``a`` ANDs four OR clauses.  Reading the literals off the gate graph, the
clauses are ``(? | c)``, ``(? | ~a | ~b)``, ``(d | ~a)`` and ``(~b | d)``,
with two unknown inputs.  Requiring the whole to be primality over 0-15
with ``a`` as the MSB forces those two to ``b`` and ``~c``: input 13
(``1101``) forces the second unknown to 1 while ``c`` is 0 and input 15
forces it to 0 while ``c`` is 1, giving ``~c``; inputs 0, 1 and 9 can then
only be excluded by the first clause, giving ``b``.  No other literal
assignment yields the primes.

The missing characters are where those two signals should run, and the page
itself shows where.  For ``~c``, the diagonal from the ``~``'s junction up
to the stranded ``.---.`` fragment crosses two horizontal runs, and the
page **already draws the ``=`` crossovers at both crossings** -- only the
single ``/`` between them is absent, so the author drew a diagonal's
crossings and omitted the diagonal.  For ``b``, a horizontal run stops four
columns short of the fragment it should reach, with nothing in between to
cross.  Both omissions are visible on the page as drawn.

Scope
-----

The exercised subset of the language is implemented: the seven gates, the
four wire characters, ``.``, ``=``, ``<``, ``>``, numeric multi-wire
labels, ``-n-`` input and ``:`` output.  Together these are every symbol the
page's sole worked example uses.

The page also specifies user-defined functions (``{name ... }``), the
constant sources ``(`` and ``)``, the wire-removal function ``{%``, the
clock ``t``, and letter-labelled wires of unfixed width -- **none of which
appear in any example on the page**, so there is no diagram to derive their
geometry from and no way to verify an implementation of them.  Each raises
:class:`ValueError` naming it as out of scope, on the same reasoning that
kept Gate out of the package: a construct the page never exercises cannot
be implemented against anything but a guess.  ``t`` would additionally make
output time-dependent, which the package treats the way it treats unseeded
randomness.

Malformed programs -- an unknown character, a gate with the wrong number of
inputs, a wiring that both feeds and is fed by one gate, or a multi-wire
label inconsistent with the width its wiring carries -- raise
:class:`ValueError`.
"""

import sys
from collections.abc import Iterator

from esolangs.interpreters.io import IO

# Wire characters, and the directions each one accepts a connection from.
# A direction is (dx, dy) pointing *out* of the cell, y growing downward.
_UP = (0, -1)
_DOWN = (0, 1)
_LEFT = (-1, 0)
_RIGHT = (1, 0)
_UP_LEFT = (-1, -1)
_UP_RIGHT = (1, -1)
_DOWN_LEFT = (-1, 1)
_DOWN_RIGHT = (1, 1)

_DIAGONALS = (_UP_LEFT, _UP_RIGHT, _DOWN_LEFT, _DOWN_RIGHT)
_ORTHOGONALS = (_UP, _DOWN, _LEFT, _RIGHT)
_ALL_DIRECTIONS = _ORTHOGONALS + _DIAGONALS

# Which directions each wire character reaches in.  ``.`` reaches every
# neighbour; the rest reach only along their own shape.  ``=`` is absent
# because it is not a wiring member at all -- it passes a connection
# through to the far side (see ``_through``).
_WIRE_DIRECTIONS = {
    "-": (_LEFT, _RIGHT),
    "|": (_UP, _DOWN),
    "/": (_UP_RIGHT, _DOWN_LEFT),
    "\\": (_UP_LEFT, _DOWN_RIGHT),
    ".": _ALL_DIRECTIONS,
}

_WIRES = frozenset(_WIRE_DIRECTIONS)
_CROSSOVER = "="

# Gates, mapped to the number of input wirings each takes.
_BINARY_GATES = frozenset("aAoOxX")
_GATES = _BINARY_GATES | frozenset("~")

# The splitter and combiner.  Both are gate-like: they read on the left and
# drive on the right, but they rearrange wire counts rather than compute.
_SPLIT = "<"
_COMBINE = ">"

_OUTPUT = ":"

# Specified by the page but exercised by none of its examples; see the
# module docstring's scope section.
_OUT_OF_SCOPE = {
    "{": "user-defined functions",
    "}": "user-defined functions",
    "(": "the constant-0 source '('",
    ")": "the constant-1 source ')'",
    "%": "the wire-removal function '{%'",
    "?": "the splitter/combiner primitive '?'",
    "t": "the clock 't'",
}


def _opposite(direction: tuple[int, int]) -> tuple[int, int]:
    """Return the direction pointing the other way along the same line."""
    dx, dy = direction
    return (-dx, -dy)


class _Grid:
    """The program text as a rectangular character grid."""

    def __init__(self, code: list[str]) -> None:
        """Store ``code`` padded to a common width."""
        self.rows = [line.rstrip("\n") for line in code]
        self.width = max((len(r) for r in self.rows), default=0)
        self.rows = [r.ljust(self.width) for r in self.rows]
        self.height = len(self.rows)

    def at(self, x: int, y: int) -> str:
        """Return the character at ``(x, y)``, or a space when off-grid."""
        if 0 <= y < self.height and 0 <= x < self.width:
            return self.rows[y][x]
        return " "

    def cells(self) -> Iterator[tuple[int, int, str]]:
        """Yield ``(x, y, char)`` for every cell, in reading order."""
        for y, row in enumerate(self.rows):
            for x, char in enumerate(row):
                yield x, y, char


class _Wiring:
    """One group of mutually connected wires, holding a single value.

    ``cells`` is every wire cell in the group, ``width`` the number of
    wires it carries (1 unless a ``-n-`` label widens it), and ``value`` a
    tuple of ``width`` bits, or ``None`` while the wiring is Null.
    """

    def __init__(self, cells: frozenset[tuple[int, int]]) -> None:
        """Create a Null wiring covering ``cells``."""
        self.cells = cells
        self.width = 1
        self.labelled = False
        self.value: tuple[int, ...] | None = None


class _Connections:
    """The connection graph derived from a grid's wire characters.

    Connections are mutual: ``reaches`` decides whether a cell extends a
    wire in some direction, and two neighbours are joined only when each
    reaches the other.  ``=`` is a crossover rather than a wire, so a
    connection arriving at one passes straight through to the far side,
    repeating while further ``=``s are met.
    """

    def __init__(self, grid: _Grid) -> None:
        """Build the connection graph for ``grid``."""
        self.grid = grid

    def reaches(self, x: int, y: int, direction: tuple[int, int]) -> bool:
        """Return whether the wire at ``(x, y)`` extends in ``direction``."""
        char = self.grid.at(x, y)
        directions = _WIRE_DIRECTIONS.get(char)
        return directions is not None and direction in directions

    def through(
        self, x: int, y: int, direction: tuple[int, int]
    ) -> tuple[int, int] | None:
        """Follow ``direction`` from ``(x, y)``, crossing any ``=`` chain.

        Returns the first non-crossover cell reached, or ``None`` when the
        chain runs off the grid.  A ``=`` extends the connection one more
        character, and the prime tester's ``.===.`` chains three of them,
        so the walk repeats rather than hopping a single cell.
        """
        dx, dy = direction
        nx, ny = x + dx, y + dy
        while self.grid.at(nx, ny) == _CROSSOVER:
            nx, ny = nx + dx, ny + dy
            if not (0 <= ny < self.grid.height and 0 <= nx < self.grid.width):
                return None
        if not (0 <= ny < self.grid.height and 0 <= nx < self.grid.width):
            return None
        return nx, ny

    def neighbours(self, x: int, y: int) -> list[tuple[int, int]]:
        """Return the wire cells mutually connected to the wire at ``(x, y)``.

        Only directions this cell reaches in are tried, and the cell found
        must reach back along the same line -- the spec's requirement that a
        wire be "connected both ways", which is what makes ``-|`` and
        ``.|`` non-connections.
        """
        found = []
        for direction in _ALL_DIRECTIONS:
            if not self.reaches(x, y, direction):
                continue
            target = self.through(x, y, direction)
            if target is None:
                continue
            if self.reaches(target[0], target[1], _opposite(direction)):
                found.append(target)
        return found


class _Gate:
    """One gate, splitter, combiner or output port.

    ``kind`` is the character drawn, ``inputs`` the wirings feeding it in
    top-to-bottom order, and ``outputs`` the wirings it drives, likewise
    ordered.  ``x``/``y`` locate it for error messages and for the reading
    order in which outputs print.
    """

    def __init__(self, kind: str, x: int, y: int) -> None:
        """Create a gate of ``kind`` at ``(x, y)`` with no ports bound."""
        self.kind = kind
        self.x = x
        self.y = y
        self.inputs: list[_Wiring] = []
        self.outputs: list[_Wiring] = []


class _Parser:
    """Turns a grid into wirings and the gates that join them."""

    def __init__(self, grid: _Grid) -> None:
        """Parse ``grid`` into ``wirings`` and ``gates``."""
        self.grid = grid
        self.links = _Connections(grid)
        self._check_characters()
        self.wirings = self._build_wirings()
        self._label_widths()
        self.gates = self._build_gates()
        self._check_widths()

    def _check_characters(self) -> None:
        """Reject characters that are unknown or out of scope."""
        for x, y, char in self.grid.cells():
            # ``+`` only ever joins the parts of a summed wire label
            # (``-1+2-``), which ``_label_widths`` reads as a whole.
            if char == " " or char.isdigit() or char == "+":
                continue
            if char in _WIRES or char == _CROSSOVER:
                continue
            if char in _GATES or char in (_SPLIT, _COMBINE, _OUTPUT):
                continue
            if char in _OUT_OF_SCOPE:
                raise ValueError(
                    f"{_OUT_OF_SCOPE[char]} is out of scope: {char!r} at ({x}, {y})"
                )
            if char.isalpha():
                raise ValueError(
                    "letter-labelled multi-wires are out of scope: "
                    f"{char!r} at ({x}, {y})"
                )
            raise ValueError(f"unknown character {char!r} at ({x}, {y})")

    def _build_wirings(self) -> list[_Wiring]:
        """Group every wire cell into maximal connected components."""
        seen: set[tuple[int, int]] = set()
        wirings = []
        for x, y, char in self.grid.cells():
            if char not in _WIRES or (x, y) in seen:
                continue
            stack = [(x, y)]
            group: set[tuple[int, int]] = set()
            while stack:
                cell = stack.pop()
                if cell in group:
                    continue
                group.add(cell)
                stack.extend(self.links.neighbours(*cell))
            seen |= group
            wirings.append(_Wiring(frozenset(group)))
        return wirings

    def _wiring_at(self, cell: tuple[int, int]) -> _Wiring | None:
        """Return the wiring covering ``cell``, if any."""
        for wiring in self.wirings:
            if cell in wiring.cells:
                return wiring
        return None

    def _label_widths(self) -> None:
        """Apply every ``-n-`` digit run to the wiring it annotates.

        A run of digits sits *inside* a wire, splitting it visually; the
        wirings on either side are the same electrical wiring, so the label
        joins them and fixes the width for the whole group.  The spec allows
        a sum spelling (``-1+2-``), which totals to the same width.
        """
        for y in range(self.grid.height):
            x = 0
            while x < self.grid.width:
                if not self.grid.at(x, y).isdigit():
                    x += 1
                    continue
                start = x
                while x < self.grid.width and (
                    self.grid.at(x, y).isdigit() or self.grid.at(x, y) == "+"
                ):
                    x += 1
                text = "".join(self.grid.at(i, y) for i in range(start, x))
                width = self._label_width(text, start, y)
                self._apply_label(start, x, y, width)

    def _label_width(self, text: str, x: int, y: int) -> int:
        """Return the total width a ``-n-`` label spells, e.g. ``1+2`` -> 3."""
        parts = text.split("+")
        if not all(part.isdigit() for part in parts):
            raise ValueError(f"malformed wire label {text!r} at ({x}, {y})")
        width = sum(int(part) for part in parts)
        if width < 1:
            raise ValueError(f"wire label {text!r} at ({x}, {y}) must be positive")
        return width

    def _apply_label(self, start: int, end: int, y: int, width: int) -> None:
        """Join the wirings flanking a label and fix their common width.

        The label interrupts a wire, so the cells immediately left and right
        of it belong to one electrical wiring; they are merged here and the
        result carries ``width`` wires.
        """
        flanking = []
        for cell in ((start - 1, y), (end, y)):
            wiring = self._wiring_at(cell)
            if wiring is not None and wiring not in flanking:
                flanking.append(wiring)
        if not flanking:
            raise ValueError(f"wire label at ({start}, {y}) annotates no wire")

        merged = _Wiring(frozenset().union(*(w.cells for w in flanking)))
        merged.width = width
        merged.labelled = True
        for wiring in flanking:
            if wiring.labelled and wiring.width != width:
                raise ValueError(
                    f"inconsistent wire labels at ({start}, {y}): "
                    f"{wiring.width} and {width}"
                )
            self.wirings.remove(wiring)
        self.wirings.append(merged)

    def _ports(
        self,
        x: int,
        y: int,
        side: int,
        offsets: tuple[int, ...] = (-1, 0, 1),
    ) -> list[_Wiring]:
        """Return the wirings touching one side of a gate, one per port.

        ``side`` is -1 for the gate's left (its inputs) and 1 for its right
        (its outputs).  All three neighbours on that side are tried, and a
        wiring counts only when it reaches back toward the gate -- the same
        mutual-connection rule wires obey between themselves.  Results are
        ordered top to bottom, which is the order the spec gives a gate's
        two inputs and a splitter's two outputs.

        A port is counted once per *cell*, not once per wiring, because one
        wiring may legitimately feed both of a gate's inputs: the page's
        constant-output circuit runs a single wiring into both sides of its
        ``a``, which is how it holds the gate's output steady.  Only the
        crossover walk can make two directions land on one cell, and that
        is deduplicated.

        ``offsets`` selects which of the three neighbours to try, so a
        caller can narrow the side: a splitter's outputs are the two
        diagonals only, and a ``~``'s input is the level cell only.
        """
        found: list[_Wiring] = []
        seen: set[tuple[int, int]] = set()
        for dy in offsets:
            cell = self.links.through(x, y, (side, dy))
            if cell is None or cell in seen:
                continue
            if not self.links.reaches(cell[0], cell[1], (-side, -dy)):
                continue
            wiring = self._wiring_at(cell)
            if wiring is not None:
                seen.add(cell)
                found.append(wiring)
        return found

    def _build_gates(self) -> list[_Gate]:
        """Bind every gate's input and output wirings.

        A wiring may not touch both a gate's inputs and its output (the
        spec says so outright), which is what resolves the example's
        junctions where one ``.`` sits diagonally beside a gate it does not
        feed: such a cell is already the gate's output, so it is dropped
        from the input side rather than counted twice.

        ``<`` is the exception, and the spec states it directly: "any wire
        that connects to the ``<`` from the upper right or lower right
        receives the wire", so a splitter drives its two diagonals only.
        Its straight-ahead neighbour belongs to the wiring feeding it --
        the prime tester draws exactly that, a ``.`` shared between the
        splitter's input and the run continuing past it.
        """
        gates = []
        for x, y, char in self.grid.cells():
            if char not in _GATES and char not in (_SPLIT, _COMBINE, _OUTPUT):
                continue
            gate = _Gate(char, x, y)
            if char == _OUTPUT:
                outputs: list[_Wiring] = []
            elif char == _SPLIT:
                outputs = self._ports(x, y, 1, offsets=(-1, 1))
            else:
                outputs = self._ports(x, y, 1)
            incoming = self._ports(x, y, -1)
            if char == "~" and len(incoming) > 1:
                # NOT takes exactly one input, drawn level with it (the
                # spec's sample is ``.~.``), so a diagonal neighbour is
                # some other wiring routed past the gate, not an input.
                level = self._ports(x, y, -1, offsets=(0,))
                if len(level) == 1:
                    incoming = level
            inputs = [w for w in incoming if w not in outputs]
            gate.inputs = inputs
            gate.outputs = [w for w in outputs if w not in inputs]
            self._check_arity(gate)
            gates.append(gate)
        return gates

    def _check_arity(self, gate: _Gate) -> None:
        """Reject a gate whose port count the spec does not allow."""
        wanted_in = 1 if gate.kind in ("~", _SPLIT, _OUTPUT) else 2
        if len(gate.inputs) != wanted_in:
            raise ValueError(
                f"{gate.kind!r} at ({gate.x}, {gate.y}) takes {wanted_in} "
                f"input(s), found {len(gate.inputs)}"
            )
        if gate.kind == _OUTPUT:
            return
        wanted_out = 2 if gate.kind == _SPLIT else 1
        if len(gate.outputs) != wanted_out:
            raise ValueError(
                f"{gate.kind!r} at ({gate.x}, {gate.y}) drives {wanted_out} "
                f"output(s), found {len(gate.outputs)}"
            )

    def _check_widths(self) -> None:
        """Propagate multi-wire widths through the gates, checking consistency.

        A gate other than ``~`` collapses its inputs to one wire, ``~``
        preserves width, ``<`` halves (rounding down to the upper output),
        and ``>`` sums.  Widths flow forward until they stop changing, so a
        label anywhere in a chain fixes the wirings it reaches.
        """
        for _ in range(len(self.wirings) + 1):
            changed = False
            for gate in self.gates:
                for wiring, width in self._implied_widths(gate):
                    if wiring.width == width:
                        continue
                    if wiring.labelled:
                        raise ValueError(
                            f"{gate.kind!r} at ({gate.x}, {gate.y}) implies "
                            f"{width} wire(s) for a wiring labelled "
                            f"{wiring.width}"
                        )
                    wiring.width = width
                    changed = True
            if not changed:
                return
        raise ValueError("multi-wire widths do not settle")

    def _implied_widths(self, gate: _Gate) -> list[tuple[_Wiring, int]]:
        """Return the widths ``gate`` forces on its output wirings."""
        if gate.kind == _OUTPUT:
            return []
        if gate.kind == "~":
            return [(gate.outputs[0], gate.inputs[0].width)]
        if gate.kind == _SPLIT:
            total = gate.inputs[0].width
            upper = total // 2
            return [
                (gate.outputs[0], max(upper, 1)),
                (gate.outputs[1], max(total - upper, 1)),
            ]
        if gate.kind == _COMBINE:
            total = gate.inputs[0].width + gate.inputs[1].width
            return [(gate.outputs[0], total)]
        return [(gate.outputs[0], 1)]


def _apply_gate(kind: str, inputs: list[tuple[int, ...]]) -> tuple[int, ...]:
    """Return the wires ``kind`` drives given its non-null input wires.

    The multi-input readings are the spec's own: AND is 1 iff every wire is
    1, OR iff any is, XOR iff exactly one is, and the negated gates invert
    those.  ``~`` is the only gate that returns more than one wire.
    """
    if kind == "~":
        return tuple(1 - bit for bit in inputs[0])

    bits = [bit for wires in inputs for bit in wires]
    ones = sum(bits)
    if kind == "a":
        result = int(ones == len(bits))
    elif kind == "A":
        result = int(ones != len(bits))
    elif kind == "o":
        result = int(ones > 0)
    elif kind == "O":
        result = int(ones == 0)
    elif kind == "x":
        result = int(ones == 1)
    else:  # "X"
        result = int(ones != 1)
    return (result,)


class _Machine:
    """Per-run Circuit Diagram state: the wirings, the gates, their latches.

    Values are *events*, not stored charge.  Each generation a wiring's
    value is the XOR of whatever fired into it during that generation, and
    a wiring nothing drove is Null again -- which is what makes the spec's
    flip-flop alternate ``1N1N1N...`` instead of settling on a value.

    Gates bridge those events with a latch per input slot, because the spec
    says a gate "waits until the other input comes" when only one has
    arrived: a slot remembers the last non-null value it saw, and a later
    arrival on the same slot overwrites it ("the gate takes that into
    account").  A gate fires when every slot is filled *and* at least one of
    its inputs is live this generation, so a filled latch alone cannot make
    a gate fire forever.

    ``step()`` advances one generation; ``halted`` is true once a generation
    is quiescent -- nothing fired and every wiring is Null.  The machine is
    deterministic and :meth:`snapshot` is bounded, so a feedback circuit
    that never quiesces is caught by ``run_until_halt_or_cycle``; the
    latches are part of the snapshot, since two generations with equal
    wiring values but different latches are not the same state.
    """

    def __init__(self, code: list[str], io: IO) -> None:
        """Parse ``code`` and read the input its ``-n-`` ports call for."""
        self.io = io
        grid = _Grid(code)
        parsed = _Parser(grid)
        self.grid = grid
        self.wirings = parsed.wirings
        self.gates = parsed.gates
        self.halted = False
        # Each gate's remembered inputs, one slot per input wiring.
        self.latches: dict[int, list[tuple[int, ...] | None]] = {
            id(gate): [None] * len(gate.inputs) for gate in self.gates
        }
        self._load_inputs()

    def _load_inputs(self) -> None:
        """Drive every input wiring with the bits read from stdin.

        A ``-`` at the start of a line is an input port; its wiring takes as
        many bits as it is wide, most significant first (the ordering the
        prime tester's formula pins down).  Ports are read in reading order,
        so a diagram with several is fed top to bottom.  Input arrives in
        generation zero only -- it is an event like any other.
        """
        for y in range(self.grid.height):
            row = self.grid.rows[y]
            stripped = row.lstrip()
            if not stripped.startswith("-"):
                continue
            x = len(row) - len(stripped)
            wiring = self._wiring_at((x, y))
            if wiring is None or wiring.value is not None:
                continue
            wiring.value = tuple(self._read_bit() for _ in range(wiring.width))

    def _wiring_at(self, cell: tuple[int, int]) -> _Wiring | None:
        """Return the wiring covering ``cell``, if any."""
        for wiring in self.wirings:
            if cell in wiring.cells:
                return wiring
        return None

    def _read_bit(self) -> int:
        """Read one bit of input, taking exhausted input as a zero bit."""
        try:
            value = self.io.input_str()
        except (EOFError, IndexError):
            return 0
        return 1 if value.strip() == "1" else 0

    def step(self) -> None:
        """Advance one generation: latch arrivals, fire, then re-drive wires."""
        self._emit()

        pending: dict[int, list[tuple[int, ...]]] = {}
        fired = False
        for gate in self.gates:
            if gate.kind == _OUTPUT:
                continue
            slots = self.latches[id(gate)]
            live = False
            for index, wiring in enumerate(gate.inputs):
                if wiring.value is not None:
                    slots[index] = wiring.value
                    live = True
            if not live or any(slot is None for slot in slots):
                continue
            fired = True
            inputs = [slot for slot in slots if slot is not None]
            for wiring, value in self._drive(gate, inputs):
                pending.setdefault(id(wiring), []).append(value)

        quiet = not fired and all(w.value is None for w in self.wirings)
        for wiring in self.wirings:
            driven = pending.get(id(wiring))
            wiring.value = self._merge(driven) if driven else None
        if quiet:
            self.halted = True

    def _drive(
        self, gate: _Gate, inputs: list[tuple[int, ...]]
    ) -> list[tuple[_Wiring, tuple[int, ...]]]:
        """Return the values ``gate`` writes to each of its outputs."""
        if gate.kind == _SPLIT:
            wires = inputs[0]
            upper = gate.outputs[0].width
            return [
                (gate.outputs[0], wires[:upper]),
                (gate.outputs[1], wires[upper:]),
            ]
        if gate.kind == _COMBINE:
            return [(gate.outputs[0], inputs[0] + inputs[1])]
        return [(gate.outputs[0], _apply_gate(gate.kind, inputs))]

    def _merge(self, driven: list[tuple[int, ...]]) -> tuple[int, ...]:
        """Combine several drivers of one wiring by XOR, per the spec."""
        if len(driven) == 1:
            return driven[0]
        width = max(len(value) for value in driven)
        merged = [0] * width
        for value in driven:
            for i, bit in enumerate(value):
                merged[i] ^= bit
        return tuple(merged)

    def _emit(self) -> None:
        """Print each ``:`` whose wire carries a value this generation."""
        for gate in self.gates:
            if gate.kind != _OUTPUT:
                continue
            value = gate.inputs[0].value
            if value is not None:
                self.io.print_str("".join(str(bit) for bit in value))

    def snapshot(self) -> tuple[object, ...]:
        """Return the machine's state, hashable for cycle detection."""
        return (
            tuple(w.value for w in self.wirings),
            tuple(tuple(self.latches[id(g)]) for g in self.gates),
            self.halted,
        )


def run(code: list[str], io: IO) -> None:
    """Execute a Circuit Diagram program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.readlines(), IO())
