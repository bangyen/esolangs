r"""Interpreter for Circuit Diagram.

Wires (``-``, ``|``, ``/``, ``\``) join gates, and the grid runs as a
cellular automaton: a gate drives its output wiring in the *next*
generation once every input slot holds a value and one has just
arrived.  There is no instruction pointer.  Gates (per the wiki): ``a``
AND, ``A`` NAND, ``o`` OR, ``O`` NOR, ``x`` XOR (exactly one input 1),
``X`` XNOR, ``~`` NOT (as many wires as it took).  All but ``~`` take two
inputs from the left and drive one output right.  ``<`` splits a
multi-wire in half, ``>`` appends its second input to its first, and ``%``
removes a leading slice.  Numeric and letter expressions label widths;
``(``, ``)``, and ``t`` source zeroes, ones, and the 32-bit clock.
A leading ``-`` reads input and ``:`` prints the wire to its left.

A *wiring* is a group of wires connected without passing a gate and
holds one value (Null, 0, 1, or a tuple).  Wires connect only when they
point at each other ("connected both ways"), so ``-|`` and ``.|`` are
non-connections; ``.`` connects to all eight neighbours; ``=`` is a
crossover that chains (the prime tester's ``.===.``).

Judgment calls, each resolved against the page's 4-bit prime tester,
which the suite replays over all sixteen inputs:

* **Values are events, and gates latch them.**  Sticky wirings are
  falsified by the page's flip-flop, which outputs ``1N1N1N...``; so a
  value lasts one generation (XOR of what fired into it, else Null).
  Per "the gate waits until the other input comes", each gate keeps a
  latch per input slot, overwritten by each non-null arrival, and fires
  when every slot is filled *and* one input is live -- which stops a
  filled latch re-firing forever.  ``:`` prints whenever its wire
  carries a value; a program halts on a quiescent generation.  Feedback
  circuits are bounded by :func:`esolangs.vm.run_until_halt_or_cycle`
  (the flip-flop is period 2), and latches are part of
  :meth:`_Machine.snapshot`.
* **Wire 1 is the first bit read and the MSB**: the only ordering under
  which the example's formula is primality.
* **Input format**: one line per bit, ``1`` is one, anything else zero,
  as Flowchart already does.
* **Gate ports are direction-sets.**  The prime tester feeds ``<`` from
  the upper-left ``/`` on one line and the lower-left ``\`` on another,
  so a gate accepts any of its three left neighbours and drives any of
  its three right ones, under the spec's rule that **one wiring may not
  touch both a gate's inputs and its output**.  ``<`` drives only its two
  right diagonals ("from the upper right or lower right"), ``~`` takes
  only the level cell (``.~.``), and one wiring may feed both slots of a
  gate (the constant-output circuit), so ports count per cell.

The page's prime tester is missing five characters and as drawn prints
nothing: two OR gates have an undriven input.
``tests/interpreters/test_circuit_diagram.py`` carries ``PRIME_TESTER``
(repaired, replayed over sixteen inputs) and ``PRIME_TESTER_AS_DRAWN``
(silence pinned).  The repair is derived and unique: the circuit is a
product of sums ``(? | c)``, ``(? | ~a | ~b)``, ``(d | ~a)``,
``(~b | d)``; primality over 0-15 with ``a`` the MSB forces the unknowns
to ``~c`` (inputs 13 and 15) and ``b`` (inputs 0, 1, 9).  The page
already draws the ``=`` crossovers where ``~c``'s diagonal would cross
and omits only the ``/`` between them; ``b``'s horizontal run stops four
columns short.

Named ``{function ... }`` blocks are removed from the main grid and called
as atomic custom gates.  Their input rows bind symbolic widths at each call;
their output ports are concatenated into the call's output multi-wire.
Malformed programs (unknown character, wrong input count, a wiring
feeding and fed by one gate, an inconsistent width label) raise
:class:`ValueError`.  At EOF a read yields a **zero bit** rather than
raising, since every gate is live at once and the automaton needs a
value to settle on; no :class:`HaltError` is raised.
"""

import re
from datetime import UTC, datetime
from functools import lru_cache
from typing import Final, Literal, cast

from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO, ScriptedIO

type _Definitions = dict[str, tuple[str, ...]]

_DEFINITION_HEADER = re.compile(r"\s*\{([A-Za-z]+|[<>%])\s*")


def _split_definitions(code: list[str]) -> tuple[list[str], _Definitions]:
    """Return the main grid and the named function bodies declared around it."""
    main: list[str] = []
    definitions: _Definitions = {}
    position = 0
    while position < len(code):
        line = code[position].rstrip("\n")
        header = _DEFINITION_HEADER.fullmatch(line)
        if header is None:
            if line.strip() == "}":
                raise ValueError(
                    f"unmatched function terminator at line {position + 1}"
                )
            main.append(code[position])
            position += 1
            continue
        name = header.group(1)
        body: list[str] = []
        position += 1
        while position < len(code) and code[position].strip() != "}":
            body.append(code[position])
            position += 1
        if position == len(code):
            raise ValueError(f"unterminated function {name!r}")
        if name in definitions:
            raise ValueError(f"duplicate function {name!r}")
        if name in (_GATES | frozenset((_CLOCK,))):
            raise ValueError(f"function name {name!r} is reserved")
        if name not in (_SPLIT, _COMBINE, _REMOVE):
            definitions[name] = tuple(body)
        position += 1
    return main, definitions


# Wire characters, and the directions each one accepts a connection from.
# A direction is (d_row, d_col) pointing *out* of the cell, rows growing
# downward, so "up" is a negative row step.
_UP = (-1, 0)
_DOWN = (1, 0)
_LEFT = (0, -1)
_RIGHT = (0, 1)
_UP_LEFT = (-1, -1)
_UP_RIGHT = (-1, 1)
_DOWN_LEFT = (1, -1)
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

#: A numeric or symbolic width label, including sums such as ``n+m``.
_LABEL_RUN = re.compile(r"[A-Za-z0-9]+(?:\+[A-Za-z0-9]+)*")
_LABEL_NAME = re.compile(r"[A-Za-z]+")

#: The wire cells ``_build_wirings`` hunts for, so that it need not visit the
#: blanks -- which are most of a diagram.
_WIRE_CELL = re.compile(r"[-|/\\.]")

_WIRES = frozenset(_WIRE_DIRECTIONS)
_CROSSOVER = "="

# Gates, mapped to the number of input wirings each takes.  The logic
# gates are a closed alphabet -- the six binary ones and the inverter --
# so naming them lets the checker see _apply_gate handles every one.
_LogicGate = Literal["a", "A", "o", "O", "x", "X", "~"]

# Typed rather than bare frozensets of str, so that testing a grid
# character for membership narrows it to the gate alphabet the _Gate
# constructor and _apply_gate expect.
_BINARY_GATES: frozenset[_LogicGate] = frozenset(("a", "A", "o", "O", "x", "X"))
_GATES: frozenset[_LogicGate] = _BINARY_GATES | frozenset(("~",))

# The splitter and combiner.  Both are gate-like: they read on the left and
# drive on the right, but they rearrange wire counts rather than compute.
_SPLIT: Final = "<"
_COMBINE: Final = ">"

_OUTPUT: Final = ":"
_ZERO: Final = "("
_ONE: Final = ")"
_CLOCK: Final = "t"
_REMOVE: Final = "%"

# What a _Gate's built-in ``kind`` may be.  Named functions are cast at
# their parser boundary and carry a non-None ``body``.
_GateKind = _LogicGate | Literal["<", ">", "%", ":", "(", ")", "t"]

# Typed so membership narrows a parsed character to a built-in gate kind.
_MOVERS: frozenset[Literal["<", ">", "%", ":", "(", ")", "t"]] = frozenset(
    ("<", ">", "%", ":", "(", ")", "t")
)

#: The gate-like cells ``_build_gates`` hunts for, the counterpart of
#: ``_WIRE_CELL``.  Built from the alphabets rather than spelled again, so a
#: new gate character cannot be added without this finding it.
_GATE_CELL = re.compile(f"[{re.escape(''.join(sorted(_GATES | _MOVERS)))}]")

#: Every character a program may hold: the wires and their crossover, the
#: gates and movers, width-label characters, and the blank.
#: ``_check_characters`` asks a row what it holds that this does not, which
#: is one set operation rather than a step per cell.
_LEGAL: frozenset[str] = (
    _WIRES
    | frozenset(_CROSSOVER)
    | _GATES
    | _MOVERS
    | frozenset("0123456789+ ")
    | frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
)

# Braces are consumed before grid validation; ``?`` is legal only inside
# the built-in definitions, which are discarded in favour of their primitives.
_OUT_OF_SCOPE = {
    "{": "user-defined functions",
    "}": "user-defined functions",
    "?": "the splitter/combiner primitive '?'",
}


def _opposite(direction: tuple[int, int]) -> tuple[int, int]:
    """Return the direction pointing the other way along the same line."""
    d_row, d_col = direction
    return (-d_row, -d_col)


class _Grid:
    """The program text as a rectangular character grid."""

    def __init__(self, code: list[str]) -> None:
        """Store ``code`` padded to a common width."""
        self.rows = [line.rstrip("\n") for line in code]
        self.width = max((len(r) for r in self.rows), default=0)
        self.rows = [r.ljust(self.width) for r in self.rows]
        self.height = len(self.rows)

    def at(self, row: int, col: int) -> str:
        """Return the character at ``(row, col)``, or a space when off-grid."""
        if 0 <= row < self.height and 0 <= col < self.width:
            return self.rows[row][col]
        return " "


class _Wiring:
    """One group of mutually connected wires.

    ``cells`` and ``width`` (1 unless labelled); the value lives in the
    machine's state, indexed by position.
    """

    def __init__(self, cells: frozenset[tuple[int, int]]) -> None:
        """Create a Null wiring covering ``cells``."""
        self.cells = cells
        self.width = 1
        self.labelled = False


class _Connections:
    """The connection graph derived from a grid's wire characters.

    Connections are mutual; ``=`` passes a connection through, repeating
    across a chain.
    """

    def __init__(self, grid: _Grid) -> None:
        """Build the connection graph for ``grid``."""
        self.grid = grid

    def reaches(self, row: int, col: int, direction: tuple[int, int]) -> bool:
        """Return whether the wire at ``(row, col)`` extends in ``direction``."""
        char = self.grid.at(row, col)
        directions = _WIRE_DIRECTIONS.get(char)
        return directions is not None and direction in directions

    def through(
        self, row: int, col: int, direction: tuple[int, int]
    ) -> tuple[int, int] | None:
        """Follow ``direction`` from ``(row, col)``, crossing any ``=`` chain.

        Returns the first non-crossover cell, or ``None`` off the grid.
        """
        d_row, d_col = direction
        n_row, n_col = row + d_row, col + d_col
        # The loop needs no bounds check of its own: ``at`` reads off-grid as
        # a space, which is never the crossover, so walking past the edge
        # ends it.  The check below then rejects the off-grid cell it landed
        # on -- one guard covering both the stepped and the hopped case.
        while self.grid.at(n_row, n_col) == _CROSSOVER:
            n_row, n_col = n_row + d_row, n_col + d_col
        if not (0 <= n_row < self.grid.height and 0 <= n_col < self.grid.width):
            return None
        return n_row, n_col

    def neighbours(self, row: int, col: int) -> list[tuple[int, int]]:
        """Return the wire cells mutually connected to the wire at ``(row, col)``."""
        # The cell's own directions, read once.  Asking ``reaches`` per
        # direction fetched and classified the *same* character eight times
        # over, and then skipped six of them: a ``-`` reaches in two.
        #
        # Iterating them rather than ``_ALL_DIRECTIONS`` reorders the result.
        # That is safe precisely here: the one caller is the flood fill in
        # ``_build_wirings``, which pushes them on a stack and collects a
        # set, so the group it ends with does not depend on the order it
        # walked.  A caller that cared would have to filter _ALL_DIRECTIONS.
        directions = _WIRE_DIRECTIONS.get(self.grid.at(row, col))
        if directions is None:  # pragma: no cover - callers pass wire cells
            # Unreachable from ``_build_wirings``, which seeds from the wire
            # pattern and extends only to cells that reached back.  Kept
            # because a non-wire cell is a sensible question with a sensible
            # answer, and the alternative is a KeyError from a lookup.
            return []
        found = []
        for direction in directions:
            target = self.through(row, col, direction)
            if target is None:
                continue
            if self.reaches(target[0], target[1], _opposite(direction)):
                found.append(target)
        return found


class _Gate:
    """One gate, splitter, combiner or output port.

    ``inputs``/``outputs`` are ordered top to bottom and assigned by
    ``_build_gates`` right after construction; ``row``/``col`` order the
    printing.
    """

    inputs: list[_Wiring]
    outputs: list[_Wiring]

    def __init__(
        self,
        kind: _GateKind,
        row: int,
        col: int,
        body: tuple[str, ...] | None = None,
        definitions: _Definitions | None = None,
    ) -> None:
        """Create a gate of ``kind`` at ``(row, col)`` with no ports bound."""
        self.kind = kind
        self.row = row
        self.col = col
        self.body = body
        self.definitions = definitions or {}


class _Parser:
    """Turns a grid into wirings and the gates that join them."""

    def __init__(self, grid: _Grid, definitions: _Definitions | None = None) -> None:
        """Parse ``grid`` into ``wirings`` and ``gates``."""
        self.grid = grid
        self.definitions = definitions or {}
        self.links = _Connections(grid)
        self._check_characters()
        self.wirings = self._build_wirings()
        # Which wiring owns each cell.  Built with the wirings because both
        # the labels and every gate port ask the question by cell.
        self._by_cell = {
            cell: wiring for wiring in self.wirings for cell in wiring.cells
        }
        self._symbols: dict[str, list[_Wiring]] = {}
        self._expressions: list[tuple[_Wiring, tuple[str | int, ...]]] = []
        self._label_widths()
        self.gates = self._build_gates()
        self._check_widths()

    def _check_characters(self) -> None:
        """Reject characters that are unknown or out of scope."""
        # A row at a time, by set difference.  Every character is legal or
        # the program is rejected, so the common case is "this row holds
        # nothing new", which a set answers at C speed; only a row that
        # fails is walked cell by cell to name the offender.  Walking all of
        # them in Python cost a step per cell of an 8 MB grid.
        for row, line in enumerate(self.grid.rows):
            unknown = set(line) - _LEGAL
            if not unknown:
                continue
            # The leftmost offender, which is the one the cell-by-cell walk
            # would have reached first.  Asked for directly because every
            # path below raises: a loop looking for it could never finish.
            col = min(line.index(char) for char in unknown)
            char = line[col]
            if char in _OUT_OF_SCOPE:
                raise ValueError(
                    f"{_OUT_OF_SCOPE[char]} is out of scope: {char!r} at ({col}, {row})"
                )
            raise ValueError(f"unknown character {char!r} at ({col}, {row})")

        for row, line in enumerate(self.grid.rows):
            for match in _LABEL_NAME.finditer(line):
                text = match.group()
                if text in self.definitions:
                    continue
                if len(text) == 1 and text in (_GATES | frozenset((_CLOCK,))):
                    continue
                expression = next(
                    (
                        candidate
                        for candidate in _LABEL_RUN.finditer(line)
                        if candidate.start() <= match.start()
                        and candidate.end() >= match.end()
                    ),
                    None,
                )
                if (
                    expression is not None
                    and self.grid.at(row, expression.start() - 1) in _WIRES
                    and self.grid.at(row, expression.end()) in _WIRES
                ):
                    continue
                raise ValueError(
                    f"unknown function or wire label {text!r} "
                    f"at ({match.start()}, {row})"
                )

    def _build_wirings(self) -> list[_Wiring]:
        """Group every wire cell into maximal connected components."""
        seen: set[tuple[int, int]] = set()
        wirings = []
        for row, line in enumerate(self.grid.rows):
            for match in _WIRE_CELL.finditer(line):
                col = match.start()
                if (row, col) in seen:
                    continue
                stack = [(row, col)]
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
        """Return the wiring covering ``cell``, if any.

        A cell-keyed index; scanning every wiring was O(gates * wirings).
        """
        return self._by_cell.get(cell)

    def _label_widths(self) -> None:
        """Apply every numeric or symbolic label to the wiring it annotates.

        The label splits a wire visually, so it joins the two sides and
        fixes their width; a sum spelling (``-1+2-``) totals.
        """
        # Over the row's own string.  The rows are already padded to the
        # grid's width, so indexing one is what ``at`` does with two bounds
        # checks and a call; walking every cell that way, three times per
        # cell and once more per label character, was the largest single
        # cost in loading a program.
        for row, line in enumerate(self.grid.rows):
            for match in _LABEL_RUN.finditer(line):
                text = match.group()
                start, col = match.start(), match.end()
                if text in self.definitions:
                    continue
                if len(text) == 1 and text in (_GATES | frozenset((_CLOCK,))):
                    continue
                if self.grid.at(row, start - 1) not in _WIRES:
                    if text[0].isdigit():
                        raise ValueError(
                            f"wire label at ({start}, {row}) annotates no wire"
                        )
                    continue  # pragma: no cover - validation rejects this label
                if self.grid.at(row, col) not in _WIRES:
                    if text[0].isdigit():
                        raise ValueError(
                            f"wire label at ({start}, {row}) annotates no wire"
                        )
                    continue  # pragma: no cover - validation rejects this label
                terms: tuple[str | int, ...] = tuple(
                    int(part) if part.isdigit() else part for part in text.split("+")
                )
                width = (
                    sum(term for term in terms if isinstance(term, int))
                    if all(isinstance(term, int) for term in terms)
                    else None
                )
                if width is not None and width < 1:
                    raise ValueError(
                        f"wire label {text!r} at ({start}, {row}) must be positive"
                    )
                merged = self._apply_label(start, col, row, width)
                if len(terms) == 1 and isinstance(terms[0], str):
                    self._symbols.setdefault(terms[0], []).append(merged)
                elif width is None:
                    self._expressions.append((merged, terms))

    def _apply_label(
        self, start: int, end: int, row: int, width: int | None
    ) -> _Wiring:
        """Join the wirings flanking a label and fix their common width."""
        flanking = []
        for cell in ((row, start - 1), (row, end)):
            wiring = self._wiring_at(cell)
            if wiring is not None and wiring not in flanking:  # pragma: no branch
                flanking.append(wiring)
        if not flanking:  # pragma: no cover - both flanks were checked above
            raise ValueError(f"wire label at ({start}, {row}) annotates no wire")

        merged = _Wiring(frozenset().union(*(w.cells for w in flanking)))
        merged.width = width if width is not None else flanking[0].width
        merged.labelled = width is not None or any(w.labelled for w in flanking)
        for wiring in flanking:
            if width is not None and wiring.labelled and wiring.width != width:
                raise ValueError(
                    f"inconsistent wire labels at ({start}, {row}): "
                    f"{wiring.width} and {width}"
                )
            self.wirings.remove(wiring)
        self.wirings.append(merged)
        # The cell index follows the merge.  Every cell of a wiring that just
        # went is a cell of ``merged``, so re-pointing ``merged``'s own cells
        # covers all of them -- and missing this left ``_wiring_at`` handing
        # back wirings that were no longer in the list at all.
        for cell in merged.cells:
            self._by_cell[cell] = merged
        return merged

    def _ports(
        self,
        row: int,
        col: int,
        side: int,
        offsets: tuple[int, ...] = (-1, 0, 1),
    ) -> list[_Wiring]:
        """Return the wirings touching one side of a gate, one per port.

        ``side`` is -1 for inputs, 1 for outputs; ``offsets`` narrows the
        three neighbours (a splitter's outputs, a ``~``'s input).  A wiring
        counts only when it reaches back, ordered top to bottom.  Ports are
        counted per *cell*, since one wiring may feed both inputs; only the
        crossover walk can land two directions on one cell, deduplicated.
        """
        found: list[_Wiring] = []
        seen: set[tuple[int, int]] = set()
        for d_row in offsets:
            cell = self.links.through(row, col, (d_row, side))
            if cell is None or cell in seen:
                continue
            if not self.links.reaches(cell[0], cell[1], (-d_row, -side)):
                continue
            wiring = self._wiring_at(cell)
            # A cell that both links to and back from here is part of a
            # wiring by construction, so this always takes.
            if wiring is not None:  # pragma: no branch
                seen.add(cell)
                found.append(wiring)
        return found

    def _build_gates(self) -> list[_Gate]:
        """Bind every gate's input and output wirings.

        A wiring may not touch both a gate's inputs and its output, so a
        cell already on the output side is dropped from the inputs.  ``<``
        drives its two diagonals only; its straight-ahead neighbour belongs
        to the wiring feeding it.
        """
        gates = []
        for row, line in enumerate(self.grid.rows):
            functions = [
                match
                for match in _LABEL_NAME.finditer(line)
                if match.group() in self.definitions
            ]
            labels = [
                range(match.start(), match.end())
                for match in _LABEL_RUN.finditer(line)
                if match.group() not in self.definitions
                if self.grid.at(row, match.start() - 1) in _WIRES
                and self.grid.at(row, match.end()) in _WIRES
                and not (
                    len(match.group()) == 1
                    and match.group() in (_GATES | frozenset((_CLOCK,)))
                )
            ]
            builtins = [
                match
                for match in _GATE_CELL.finditer(line)
                if not any(
                    match.start() in range(function.start(), function.end())
                    for function in functions
                )
            ]
            candidates = [
                (match.start(), match.end(), match.group(), None) for match in builtins
            ] + [
                (
                    match.start(),
                    match.end(),
                    match.group(),
                    self.definitions[match.group()],
                )
                for match in functions
            ]
            for col, end, char, body in sorted(candidates):
                if any(col in label for label in labels):
                    continue
                # ``_GATE_CELL`` is built from these two alphabets, so one of
                # the arms always takes; they are spelled out because
                # membership is what narrows the character to ``_GateKind``,
                # which a regex match cannot do.
                if char in _GATES:
                    kind: _GateKind = char
                elif char in _MOVERS:
                    kind = char
                else:
                    kind = cast(_GateKind, char)
                gate = _Gate(kind, row, col, body, self.definitions)
                if char == _OUTPUT:
                    outputs: list[_Wiring] = []
                elif char == _SPLIT:
                    outputs = self._ports(row, col, 1, offsets=(-1, 1))
                elif char in (_ZERO, _ONE, _CLOCK):
                    outputs = self._ports(row, col, 1, offsets=(0,))
                else:
                    outputs = self._ports(row, end - 1, 1)
                incoming = (
                    [] if char in (_ZERO, _ONE, _CLOCK) else self._ports(row, col, -1)
                )
                if char == "~" and len(incoming) > 1:
                    # NOT takes exactly one input, drawn level with it (the
                    # spec's sample is ``.~.``), so a diagonal neighbour is
                    # some other wiring routed past the gate, not an input.
                    level = self._ports(row, col, -1, offsets=(0,))
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
        if gate.kind in (_ZERO, _ONE, _CLOCK):
            wanted_in = 0
        elif gate.body is not None:
            wanted_in = sum(line.lstrip().startswith("-") for line in gate.body)
        elif gate.kind in ("~", _SPLIT, _OUTPUT):
            wanted_in = 1
        else:
            wanted_in = 2
        if len(gate.inputs) != wanted_in:
            raise ValueError(
                f"{gate.kind!r} at ({gate.col}, {gate.row}) takes {wanted_in} "
                f"input(s), found {len(gate.inputs)}"
            )
        # An output sinks its wire and drives nothing, so the out-port count
        # below does not apply to it.  Parsing checks every gate, this one
        # included, so the return is taken by any program with an output.
        if gate.kind == _OUTPUT:
            return
        wanted_out = 2 if gate.kind == _SPLIT else 1
        if len(gate.outputs) != wanted_out:
            raise ValueError(
                f"{gate.kind!r} at ({gate.col}, {gate.row}) drives {wanted_out} "
                f"output(s), found {len(gate.outputs)}"
            )

    def _check_widths(self) -> None:
        """Propagate multi-wire widths through the gates, checking consistency.

        Gates collapse to one wire, ``~`` preserves, ``<`` halves (rounding
        down to the upper output), ``>`` sums; iterated to a fixed point.
        """
        for _ in range(len(self.wirings) + 1):
            changed = self._equate_symbols()
            for gate in self.gates:
                for wiring, width in self._implied_widths(gate):
                    if wiring.width == width:
                        continue
                    if wiring.labelled:
                        raise ValueError(
                            f"{gate.kind!r} at ({gate.col}, {gate.row}) implies "
                            f"{width} wire(s) for a wiring labelled "
                            f"{wiring.width}"
                        )
                    wiring.width = width
                    changed = True
            if not changed:
                return
        # Each pass fixes at least one wiring's width or stops, so the
        # fixpoint is reached within one pass per wiring; this catches a
        # flow that somehow cycles rather than letting it spin.
        raise ValueError(  # pragma: no cover - the width flow always settles
            "multi-wire widths do not settle"
        )

    def _equate_symbols(self) -> bool:
        """Give every occurrence of a letter label the same width."""
        changed = False
        widths: dict[str, int] = {
            term: 1
            for _, terms in self._expressions
            for term in terms
            if isinstance(term, str)
        }
        for name, labelled in self._symbols.items():
            wirings = {
                self._wiring_at(next(iter(old.cells))) or old for old in labelled
            }
            fixed = {w.width for w in wirings if w.labelled}
            if len(fixed) > 1:
                width_text = ", ".join(str(width) for width in sorted(fixed))
                raise ValueError(
                    f"wire label {name!r} has inconsistent widths: {width_text}"
                )
            width = next(iter(fixed), max(w.width for w in wirings))
            widths[name] = width
            for wiring in wirings:
                if wiring.width != width:
                    wiring.width = width
                    changed = True
        for old, terms in self._expressions:
            wiring = self._wiring_at(next(iter(old.cells))) or old
            width = sum(
                term if isinstance(term, int) else widths[term] for term in terms
            )
            if wiring.labelled and wiring.width != width:
                raise ValueError(
                    f"symbolic wire label implies {width} wire(s) for a wiring "
                    f"labelled {wiring.width}"
                )
            if wiring.width != width:
                wiring.width = width
                changed = True
        return changed

    def _implied_widths(self, gate: _Gate) -> list[tuple[_Wiring, int]]:
        """Return the widths ``gate`` forces on its output wirings."""
        if gate.kind == _OUTPUT:
            return []
        if gate.kind in (_ZERO, _ONE):
            return []
        if gate.kind == _CLOCK:
            return [(gate.outputs[0], 32)]
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
        if gate.kind == _REMOVE:
            total = gate.inputs[1].width - gate.inputs[0].width
            if total < 1:
                raise ValueError(
                    f"'%' at ({gate.col}, {gate.row}) removes every output wire"
                )
            return [(gate.outputs[0], total)]
        if gate.body is not None:
            inputs = tuple((0,) * wiring.width for wiring in gate.inputs)
            return [(gate.outputs[0], len(_evaluate_function(gate, inputs)))]
        return [(gate.outputs[0], 1)]


@lru_cache(maxsize=16)
def _compile(
    code: tuple[str, ...],
) -> tuple[
    _Grid,
    list[_Wiring],
    list[_Gate],
    dict[int, int],
    dict[tuple[int, int], _Wiring],
]:
    """Return the validated, read-only topology shared by public runs."""
    main, definitions = _split_definitions(list(code))
    grid = _Grid(main)
    parsed = _Parser(grid, definitions)
    wirings = parsed.wirings
    return (
        grid,
        wirings,
        parsed.gates,
        {id(wiring): i for i, wiring in enumerate(wirings)},
        {cell: wiring for wiring in wirings for cell in wiring.cells},
    )


def _apply_gate(kind: _LogicGate, inputs: list[tuple[int, ...]]) -> tuple[int, ...]:
    """Return the wires ``kind`` drives given its non-null input wires."""
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


def _drive(
    gate: "_Gate", inputs: list[tuple[int, ...]]
) -> list[tuple["_Wiring", tuple[int, ...]]]:
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
    if gate.kind == _REMOVE:
        return [(gate.outputs[0], inputs[1][len(inputs[0]) :])]
    if gate.body is not None:
        return [(gate.outputs[0], _evaluate_function(gate, tuple(inputs)))]
    if gate.kind == _OUTPUT:
        # An output gate drives nothing by definition, and ``step``
        # skips them before firing, so this is a shape rather than a
        # path: it is what lets _apply_gate take only logic gates.
        return []  # pragma: no cover - step() skips these before firing
    if gate.kind in (_ZERO, _ONE, _CLOCK):
        return []  # pragma: no cover - sources are loaded before generation one
    return [(gate.outputs[0], _apply_gate(cast(_LogicGate, gate.kind), inputs))]


def _seconds_since_2000() -> int:
    """Return the current UTC second counted from 2000-01-01."""
    epoch = datetime(2000, 1, 1, tzinfo=UTC)
    return int((datetime.now(UTC) - epoch).total_seconds()) & 0xFFFFFFFF


def _evaluate_function(
    gate: _Gate, inputs: tuple[tuple[int, ...], ...]
) -> tuple[int, ...]:
    """Evaluate one custom gate atomically for ``inputs``."""
    if gate.body is None:  # pragma: no cover - callers select custom gates
        raise ValueError(f"{gate.kind!r} has no function body")
    bindings: dict[str, int] = {}
    input_rows = [line for line in gate.body if line.lstrip().startswith("-")]
    if len(input_rows) != len(inputs):  # pragma: no cover - arity checked earlier
        raise ValueError(f"function {gate.kind!r} input count changed while running")
    for line, value in zip(input_rows, inputs, strict=True):
        labels = [
            match
            for match in _LABEL_RUN.finditer(line)
            if match.start() > 0
            and line[match.start() - 1] in _WIRES
            and match.end() < len(line)
            and line[match.end()] in _WIRES
        ]
        if not labels:
            if len(value) != 1:
                raise ValueError(
                    f"function {gate.kind!r} expects a one-wire input, "
                    f"received {len(value)}"
                )
            continue
        terms = labels[0].group().split("+")
        if all(term.isdigit() for term in terms):
            expected = sum(int(term) for term in terms)
            if expected != len(value):
                raise ValueError(
                    f"function {gate.kind!r} expects {expected} input wires, "
                    f"received {len(value)}"
                )
        elif len(terms) == 1 and terms[0].isalpha():
            old = bindings.setdefault(terms[0], len(value))
            if old != len(value):
                raise ValueError(
                    f"function {gate.kind!r} binds {terms[0]!r} "
                    f"to both {old} and {len(value)}"
                )
        else:
            raise ValueError(
                f"function {gate.kind!r} input label must be a number or one name"
            )

    expanded = []
    for line in gate.body:
        pieces: list[str] = []
        end = 0
        for match in _LABEL_RUN.finditer(line):
            if not (
                match.start() > 0
                and line[match.start() - 1] in _WIRES
                and match.end() < len(line)
                and line[match.end()] in _WIRES
            ):
                continue
            pieces.append(line[end : match.start()])
            terms = match.group().split("+")
            pieces.append("+".join(str(bindings.get(term, term)) for term in terms))
            end = match.end()
        pieces.append(line[end:])
        expanded.append("".join(pieces))

    declarations = [
        line
        for name, body in gate.definitions.items()
        for line in (f"{{{name}", *body, "}")
    ]
    stdin = "".join(f"{bit}\n" for value in inputs for bit in value)
    io = ScriptedIO(stdin)
    machine = _Machine(declarations + expanded, io)
    seen: set[tuple[object, ...]] = set()
    emitted: list[str] = []
    while not machine.halted:
        snapshot = machine.snapshot()
        if snapshot in seen:
            raise ValueError(f"function {gate.kind!r} does not settle")
        seen.add(snapshot)
        emitted.extend(
            _emitted((machine.values, machine.latches), machine.wirings, machine.gates)
        )
        machine.step()
    output = "".join(emitted)
    if not output or set(output) - {"0", "1"}:
        raise ValueError(f"function {gate.kind!r} did not return bits")
    return tuple(int(bit) for bit in output)


def _merge(driven: list[tuple[int, ...]]) -> tuple[int, ...]:
    """Combine several drivers of one wiring by XOR, per the spec."""
    if len(driven) == 1:
        return driven[0]
    width = max(len(value) for value in driven)
    merged = [0] * width
    for value in driven:
        for i, bit in enumerate(value):
            merged[i] ^= bit
    return tuple(merged)


#: One instant of a run: the value on each wiring and each gate's latched
#: inputs, both indexed by position.  A value, not a record: a generation
#: returns a new pair rather than editing the wirings in place.
#:
#: The wirings and gates themselves stay out: a diagram is parsed once and
#: never rewrites itself, so they are handed to the transition.
type _Values = tuple[tuple[int, ...] | None, ...]
type _Latches = tuple[tuple[tuple[int, ...] | None, ...], ...]
type _State = tuple[_Values, _Latches]


def _emitted(
    state: _State, wirings: list["_Wiring"], gates: list["_Gate"]
) -> list[str]:
    """Return what each ``:`` gate writes this generation, in gate order."""
    values, _ = state
    index = {id(w): i for i, w in enumerate(wirings)}
    out = []
    for gate in gates:
        if gate.kind != _OUTPUT:
            continue
        value = values[index[id(gate.inputs[0])]]
        if value is not None:
            out.append("".join(str(bit) for bit in value))
    return out


def _generation(
    state: _State, wirings: list["_Wiring"], gates: list["_Gate"]
) -> tuple[_State, bool]:
    """Return the state after one generation, and whether the run went quiet.

    Latch arrivals, fire every gate whose slots are full, re-drive every
    wiring; a wiring nothing drove goes Null again.
    """
    values, latches = state
    index = {id(w): i for i, w in enumerate(wirings)}

    pending: dict[int, list[tuple[int, ...]]] = {}
    fired = False
    grown = list(latches)
    for position, gate in enumerate(gates):
        if gate.kind in (_OUTPUT, _ZERO, _ONE, _CLOCK):
            continue
        slots = list(latches[position])
        live = False
        for slot, wiring in enumerate(gate.inputs):
            arrived = values[index[id(wiring)]]
            if arrived is not None:
                slots[slot] = arrived
                live = True
        grown[position] = tuple(slots)
        if not live or any(slot is None for slot in slots):
            continue
        fired = True
        inputs = [slot for slot in slots if slot is not None]
        for wiring, value in _drive(gate, inputs):
            pending.setdefault(index[id(wiring)], []).append(value)

    quiet = not fired and all(value is None for value in values)
    driven = tuple(
        _merge(pending[i]) if i in pending else None for i in range(len(wirings))
    )
    return (driven, tuple(grown)), quiet


class _Machine:
    """Per-run Circuit Diagram state: the wirings, the gates, their latches.

    Values are events (see the module docstring); ``halted`` is true once
    a generation is quiescent.  Latches are part of :meth:`snapshot`.
    """

    #: Whether a read past the end of the input yields a *value* here
    #: rather than raising.  Six languages do; the other 59 raise
    #: :class:`~esolangs.exceptions.InputExhaustedError`, which is the
    #: package norm and what :func:`esolangs.run` documents; this one does
    #: not, so an underfed program answers a different row of its table
    #: instead of refusing, and a caller has no way to tell from the output
    #: that it happened.
    #:
    #: Declared rather than changed.  The zero-beyond-input convention was
    #: audited against every wiki page and settled deliberately
    #: (``docs/limitations.md``, Interpreter conventions); rewriting it
    #: would be a decision about what these languages *mean*, not a fix.
    #: What was wrong was that nothing said so, so the promise ``run`` made
    #: was false for seven languages and a generic caller could not find
    #: out which.
    eof_is_a_value = True

    def __init__(self, code: list[str], io: IO) -> None:
        """Parse ``code`` and read the input its ``-n-`` ports call for."""
        self.io = io
        main, definitions = _split_definitions(code)
        grid = _Grid(main)
        parsed = _Parser(grid, definitions)
        self.grid = grid
        self.wirings = parsed.wirings
        self.gates = parsed.gates
        self.halted = False
        # The value on each wiring and each gate's remembered inputs, both
        # indexed by position rather than by ``id``: the wirings and gates
        # are fixed once parsed, so a position is a stable name and the
        # whole state is two tuples.
        self.index = {id(w): i for i, w in enumerate(self.wirings)}
        self._by_cell = {
            cell: wiring for wiring in self.wirings for cell in wiring.cells
        }
        self.values: tuple[tuple[int, ...] | None, ...] = (None,) * len(self.wirings)
        self.latches: tuple[tuple[tuple[int, ...] | None, ...], ...] = tuple(
            (None,) * len(gate.inputs) for gate in self.gates
        )
        self._load_inputs()
        self._load_sources()

    @classmethod
    def _for_run(cls, code: list[str], io: IO) -> "_Machine":
        """Return fresh state over the source's cached static topology."""
        machine = cls.__new__(cls)
        machine.io = io
        (
            machine.grid,
            machine.wirings,
            machine.gates,
            machine.index,
            machine._by_cell,  # noqa: SLF001 -- alternate constructor
        ) = _compile(tuple(code))
        machine.halted = False
        machine.values = (None,) * len(machine.wirings)
        machine.latches = tuple((None,) * len(gate.inputs) for gate in machine.gates)
        machine._load_inputs()  # noqa: SLF001 -- alternate constructor
        machine._load_sources()  # noqa: SLF001 -- alternate constructor
        return machine

    def _load_inputs(self) -> None:
        """Drive every input wiring with the bits read from stdin.

        As many bits as the port is wide, MSB first, ports in reading
        order, in generation zero only.
        """
        for row in range(self.grid.height):
            line = self.grid.rows[row]
            stripped = line.lstrip()
            if not stripped.startswith("-"):
                continue
            col = len(line) - len(stripped)
            wiring = self._wiring_at((row, col))
            # A row opening on "-" always has its own unvalued wiring: the
            # wirings are built from those very cells, and each input row is
            # read once.
            if wiring is None:  # pragma: no cover - see above
                continue
            position = self.index[id(wiring)]
            if self.values[position] is not None:  # pragma: no cover - see above
                continue
            value = tuple(self._read_bit() for _ in range(wiring.width))
            self.values = (
                *self.values[:position],
                value,
                *self.values[position + 1 :],
            )

    def _wiring_at(self, cell: tuple[int, int]) -> _Wiring | None:
        """Return the wiring covering ``cell``, if any."""
        return self._by_cell.get(cell)

    def _read_bit(self) -> int:
        """Read one bit of input, taking exhausted input as a zero bit."""
        try:
            value = self.io.input_str()
        except (EOFError, IndexError):
            return 0
        return 1 if value.strip() == "1" else 0

    def _load_sources(self) -> None:
        """Drive constants and the clock in generation zero."""
        seconds = _seconds_since_2000()
        for gate in self.gates:
            if gate.kind not in (_ZERO, _ONE, _CLOCK):
                continue
            wiring = gate.outputs[0]
            if gate.kind == _CLOCK:
                value = tuple(int(bit) for bit in f"{seconds:032b}")
            else:
                bit = int(gate.kind == _ONE)
                value = (bit,) * wiring.width
            position = self.index[id(wiring)]
            old = self.values[position]
            driven = [value] if old is None else [old, value]
            self.values = (
                *self.values[:position],
                _merge(driven),
                *self.values[position + 1 :],
            )

    # The VM's language-shaped view.

    @property
    def ip(self) -> None:
        """Always ``None``: nothing moves through a Circuit Diagram.

        ``ip_shape = "opaque"`` for the same reason: no breakpoint can name
        a place.
        """
        return None

    #: Never a place in the source, because it is never anything at all.
    ip_shape = "opaque"

    @property
    def memory(self) -> list[int]:
        """The bits driven this generation, in wiring order.

        Events, not stored charge, so the length varies per step.
        """
        return [bit for value in self.values if value is not None for bit in value]

    @property
    def stack(self) -> list[object]:
        """Circuit Diagram has no stack."""
        return []

    def step(self) -> None:
        """Advance one generation: latch arrivals, fire, then re-drive wires.

        Every ``:`` gate whose wire carries a value prints, in gate order.
        """
        for text in _emitted((self.values, self.latches), self.wirings, self.gates):
            self.io.print_str(text)
        (self.values, self.latches), halted = _generation(
            (self.values, self.latches), self.wirings, self.gates
        )
        if halted:
            self.halted = True

    def snapshot(self) -> tuple[object, ...]:
        """Return the machine's state, hashable for cycle detection."""
        # The two halves of the state are already the tuples this wants,
        # which is what freezing them bought: no per-call rebuild.
        return (self.values, self.latches, self.halted)


def run(code: list[str], io: IO) -> None:
    """Execute a Circuit Diagram program."""
    machine = _Machine._for_run(code, io)  # noqa: SLF001 -- public fast path
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    script_main(run, shape="keep")
