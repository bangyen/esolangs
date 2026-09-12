r"""Interpreter for Circuit Diagram."""

import sys
from collections.abc import Iterator
from typing import Final, Literal

from esolangs.interpreters.io import IO

# Wire characters, and the.
# A direction is (d_row, d_col).
# downward, so "up" is a.
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

# Which directions each wire.
# neighbour; the rest reach.
# because it is not a wiring.
# through to the far side (see.
_WIRE_DIRECTIONS = {
    "-": (_LEFT, _RIGHT),
    "|": (_UP, _DOWN),
    "/": (_UP_RIGHT, _DOWN_LEFT),
    "\\": (_UP_LEFT, _DOWN_RIGHT),
    ".": _ALL_DIRECTIONS,
}

_WIRES = frozenset(_WIRE_DIRECTIONS)
_CROSSOVER = "="

# Gates, mapped to the number.
# gates are a closed alphabet.
# so naming them lets the.
_LogicGate = Literal["a", "A", "o", "O", "x", "X", "~"]

# Typed rather than bare.
# character for membership.
# constructor and _apply_gate.
_BINARY_GATES: frozenset[_LogicGate] = frozenset(("a", "A", "o", "O", "x", "X"))
_GATES: frozenset[_LogicGate] = _BINARY_GATES | frozenset(("~",))

# The splitter and combiner.
# drive on the right, but they.
_SPLIT: Final = "<"
_COMBINE: Final = ">"

_OUTPUT: Final = ":"

# What a _Gate's ``kind`` may.
# gate-like characters that.
_GateKind = _LogicGate | Literal["<", ">", ":"]

# The gate-like trio as a typed.
# constants above cannot narrow.
_MOVERS: frozenset[Literal["<", ">", ":"]] = frozenset(("<", ">", ":"))

# Specified by the page but.
# module docstring's scope.
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
    r"""Return the direction pointing the other way along the same line."""
    d_row, d_col = direction
    return (-d_row, -d_col)


class _Grid:
    r"""The program text as a rectangular character grid."""

    def __init__(self, code: list[str]) -> None:
        r"""Store ``code`` padded to a common width."""
        self.rows = [line.rstrip("\n") for line in code]
        self.width = max((len(r) for r in self.rows), default=0)
        self.rows = [r.ljust(self.width) for r in self.rows]
        self.height = len(self.rows)

    def at(self, row: int, col: int) -> str:
        r"""Return the character at ``(row, col)``, or a space when off-grid."""
        if 0 <= row < self.height and 0 <= col < self.width:
            return self.rows[row][col]
        return " "

    def cells(self) -> Iterator[tuple[int, int, str]]:
        r"""Yield ``(row, col, char)`` for every cell, in reading order."""
        for row, line in enumerate(self.rows):
            for col, char in enumerate(line):
                yield row, col, char


class _Wiring:
    r"""One group of mutually connected wires."""

    def __init__(self, cells: frozenset[tuple[int, int]]) -> None:
        r"""Create a Null wiring covering ``cells``."""
        self.cells = cells
        self.width = 1
        self.labelled = False


class _Connections:
    r"""The connection graph derived from a grid's wire characters."""

    def __init__(self, grid: _Grid) -> None:
        r"""Build the connection graph for ``grid``."""
        self.grid = grid

    def reaches(self, row: int, col: int, direction: tuple[int, int]) -> bool:
        r"""Return whether the wire at ``(row, col)`` extends in ``direction``."""
        char = self.grid.at(row, col)
        directions = _WIRE_DIRECTIONS.get(char)
        return directions is not None and direction in directions

    def through(
        self, row: int, col: int, direction: tuple[int, int]
    ) -> tuple[int, int] | None:
        r"""Follow ``direction`` from ``(row, col)``, crossing any ``=`` chain."""
        d_row, d_col = direction
        n_row, n_col = row + d_row, col + d_col
        # The loop needs no bounds.
        # a space, which is never the.
        # ends it.
        # on -- one guard covering both.
        while self.grid.at(n_row, n_col) == _CROSSOVER:
            n_row, n_col = n_row + d_row, n_col + d_col
        if not (0 <= n_row < self.grid.height and 0 <= n_col < self.grid.width):
            return None
        return n_row, n_col

    def neighbours(self, row: int, col: int) -> list[tuple[int, int]]:
        r"""Return the wire cells mutually connected to the wire at ``(row,."""
        found = []
        for direction in _ALL_DIRECTIONS:
            if not self.reaches(row, col, direction):
                continue
            target = self.through(row, col, direction)
            if target is None:
                continue
            if self.reaches(target[0], target[1], _opposite(direction)):
                found.append(target)
        return found


class _Gate:
    r"""One gate, splitter, combiner or output port."""

    inputs: list[_Wiring]
    outputs: list[_Wiring]

    def __init__(self, kind: _GateKind, row: int, col: int) -> None:
        r"""Create a gate of ``kind`` at ``(row, col)`` with no ports bound."""
        self.kind = kind
        self.row = row
        self.col = col


class _Parser:
    r"""Turns a grid into wirings and the gates that join them."""

    def __init__(self, grid: _Grid) -> None:
        r"""Parse ``grid`` into ``wirings`` and ``gates``."""
        self.grid = grid
        self.links = _Connections(grid)
        self._check_characters()
        self.wirings = self._build_wirings()
        self._label_widths()
        self.gates = self._build_gates()
        self._check_widths()

    def _check_characters(self) -> None:
        r"""Reject characters that are unknown or out of scope."""
        for row, col, char in self.grid.cells():
            # ``+`` only ever joins the.
            # (``-1+2-``), which.
            if char == " " or char.isdigit() or char == "+":
                continue
            if char in _WIRES or char == _CROSSOVER:
                continue
            if char in _GATES or char in (_SPLIT, _COMBINE, _OUTPUT):
                continue
            if char in _OUT_OF_SCOPE:
                raise ValueError(
                    f"{_OUT_OF_SCOPE[char]} is out of scope: {char!r} at ({col}, {row})"
                )
            if char.isalpha():
                raise ValueError(
                    "letter-labelled multi-wires are out of scope: "
                    f"{char!r} at ({col}, {row})"
                )
            raise ValueError(f"unknown character {char!r} at ({col}, {row})")

    def _build_wirings(self) -> list[_Wiring]:
        r"""Group every wire cell into maximal connected components."""
        seen: set[tuple[int, int]] = set()
        wirings = []
        for row, col, char in self.grid.cells():
            if char not in _WIRES or (row, col) in seen:
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
        r"""Return the wiring covering ``cell``, if any."""
        for wiring in self.wirings:
            if cell in wiring.cells:
                return wiring
        return None

    def _label_widths(self) -> None:
        r"""Apply every ``-n-`` digit run to the wiring it annotates."""
        for row in range(self.grid.height):
            col = 0
            while col < self.grid.width:
                if not self.grid.at(row, col).isdigit():
                    col += 1
                    continue
                start = col
                while col < self.grid.width and (
                    self.grid.at(row, col).isdigit() or self.grid.at(row, col) == "+"
                ):
                    col += 1
                text = "".join(self.grid.at(row, i) for i in range(start, col))
                width = self._label_width(text, row, start)
                self._apply_label(start, col, row, width)

    def _label_width(self, text: str, row: int, col: int) -> int:
        r"""Return the total width a ``-n-`` label spells, e.g."""
        parts = text.split("+")
        if not all(part.isdigit() for part in parts):
            raise ValueError(f"malformed wire label {text!r} at ({col}, {row})")
        width = sum(int(part) for part in parts)
        if width < 1:
            raise ValueError(f"wire label {text!r} at ({col}, {row}) must be positive")
        return width

    def _apply_label(self, start: int, end: int, row: int, width: int) -> None:
        r"""Join the wirings flanking a label and fix their common width."""
        flanking = []
        for cell in ((row, start - 1), (row, end)):
            wiring = self._wiring_at(cell)
            if wiring is not None and wiring not in flanking:
                flanking.append(wiring)
        if not flanking:
            raise ValueError(f"wire label at ({start}, {row}) annotates no wire")

        merged = _Wiring(frozenset().union(*(w.cells for w in flanking)))
        merged.width = width
        merged.labelled = True
        for wiring in flanking:
            if wiring.labelled and wiring.width != width:
                raise ValueError(
                    f"inconsistent wire labels at ({start}, {row}): "
                    f"{wiring.width} and {width}"
                )
            self.wirings.remove(wiring)
        self.wirings.append(merged)

    def _ports(
        self,
        row: int,
        col: int,
        side: int,
        offsets: tuple[int, ...] = (-1, 0, 1),
    ) -> list[_Wiring]:
        r"""Return the wirings touching one side of a gate, one per port."""
        found: list[_Wiring] = []
        seen: set[tuple[int, int]] = set()
        for d_row in offsets:
            cell = self.links.through(row, col, (d_row, side))
            if cell is None or cell in seen:
                continue
            if not self.links.reaches(cell[0], cell[1], (-d_row, -side)):
                continue
            wiring = self._wiring_at(cell)
            # A cell that both links to and.
            # wiring by construction, so.
            if wiring is not None:  # pragma: no branch
                seen.add(cell)
                found.append(wiring)
        return found

    def _build_gates(self) -> list[_Gate]:
        r"""Bind every gate's input and output wirings."""
        gates = []
        for row, col, char in self.grid.cells():
            if char in _GATES:
                kind: _GateKind = char
            elif char in _MOVERS:
                kind = char
            else:
                continue
            gate = _Gate(kind, row, col)
            if char == _OUTPUT:
                outputs: list[_Wiring] = []
            elif char == _SPLIT:
                outputs = self._ports(row, col, 1, offsets=(-1, 1))
            else:
                outputs = self._ports(row, col, 1)
            incoming = self._ports(row, col, -1)
            if char == "~" and len(incoming) > 1:
                # NOT takes exactly one input,.
                # spec's sample is ``.~.``), so.
                # some other wiring routed past.
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
        r"""Reject a gate whose port count the spec does not allow."""
        wanted_in = 1 if gate.kind in ("~", _SPLIT, _OUTPUT) else 2
        if len(gate.inputs) != wanted_in:
            raise ValueError(
                f"{gate.kind!r} at ({gate.col}, {gate.row}) takes {wanted_in} "
                f"input(s), found {len(gate.inputs)}"
            )
        # An output sinks its wire and.
        # below does not apply to it.
        # included, so the return is.
        if gate.kind == _OUTPUT:
            return
        wanted_out = 2 if gate.kind == _SPLIT else 1
        if len(gate.outputs) != wanted_out:
            raise ValueError(
                f"{gate.kind!r} at ({gate.col}, {gate.row}) drives {wanted_out} "
                f"output(s), found {len(gate.outputs)}"
            )

    def _check_widths(self) -> None:
        r"""Propagate multi-wire widths through the gates, checking consistency."""
        for _ in range(len(self.wirings) + 1):
            changed = False
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
        # Each pass fixes at least one.
        # fixpoint is reached within.
        # flow that somehow cycles.
        raise ValueError(  # pragma: no cover - the width flow always settles
            "multi-wire widths do not settle"
        )

    def _implied_widths(self, gate: _Gate) -> list[tuple[_Wiring, int]]:
        r"""Return the widths ``gate`` forces on its output wirings."""
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


def _apply_gate(kind: _LogicGate, inputs: list[tuple[int, ...]]) -> tuple[int, ...]:
    r"""Return the wires ``kind`` drives given its non-null input wires."""
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
    else:  # "X".
        result = int(ones != 1)
    return (result,)


def _drive(
    gate: "_Gate", inputs: list[tuple[int, ...]]
) -> list[tuple["_Wiring", tuple[int, ...]]]:
    r"""Return the values ``gate`` writes to each of its outputs."""
    if gate.kind == _SPLIT:
        wires = inputs[0]
        upper = gate.outputs[0].width
        return [
            (gate.outputs[0], wires[:upper]),
            (gate.outputs[1], wires[upper:]),
        ]
    if gate.kind == _COMBINE:
        return [(gate.outputs[0], inputs[0] + inputs[1])]
    if gate.kind == _OUTPUT:
        # An output gate drives nothing.
        # skips them before firing, so.
        # path: it is what lets.
        return []  # pragma: no cover - step() skips these before firing
    return [(gate.outputs[0], _apply_gate(gate.kind, inputs))]


def _merge(driven: list[tuple[int, ...]]) -> tuple[int, ...]:
    r"""Combine several drivers of one wiring by XOR, per the spec."""
    if len(driven) == 1:
        return driven[0]
    width = max(len(value) for value in driven)
    merged = [0] * width
    for value in driven:
        for i, bit in enumerate(value):
            merged[i] ^= bit
    return tuple(merged)


# : One instant of a run: the.
# : inputs, both indexed by.
# : returns a new pair rather.
# :.
# : The wirings and gates.
# : never rewrites itself, so.
type _Values = tuple[tuple[int, ...] | None, ...]
type _Latches = tuple[tuple[tuple[int, ...] | None, ...], ...]
type _State = tuple[_Values, _Latches]


def _emitted(
    state: _State, wirings: list["_Wiring"], gates: list["_Gate"]
) -> list[str]:
    r"""Return what each ``:`` gate writes this generation, in gate order."""
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
    r"""Return the state after one generation, and whether the run went."""
    values, latches = state
    index = {id(w): i for i, w in enumerate(wirings)}

    pending: dict[int, list[tuple[int, ...]]] = {}
    fired = False
    grown = list(latches)
    for position, gate in enumerate(gates):
        if gate.kind == _OUTPUT:
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
    r"""Per-run Circuit Diagram state: the wirings, the gates, their."""

    # : Whether a read past the end.
    # : rather than raising.
    # :.
    # : package norm and what.
    # : not, so an underfed program.
    # : instead of refusing, and a.
    #: that it happened.
    # :.
    # : Declared rather than.
    # : audited against every wiki.
    # : (``docs/limitations.md``,.
    # : would be a decision about.
    # : What was wrong was that.
    # : was false for seven.
    #: out which.
    eof_is_a_value = True

    def __init__(self, code: list[str], io: IO) -> None:
        r"""Parse ``code`` and read the input its ``-n-`` ports call for."""
        self.io = io
        grid = _Grid(code)
        parsed = _Parser(grid)
        self.grid = grid
        self.wirings = parsed.wirings
        self.gates = parsed.gates
        self.halted = False
        # The value on each wiring and.
        # indexed by position rather.
        # are fixed once parsed, so a.
        # whole state is two tuples.
        self.index = {id(w): i for i, w in enumerate(self.wirings)}
        self.values: tuple[tuple[int, ...] | None, ...] = (None,) * len(self.wirings)
        self.latches: tuple[tuple[tuple[int, ...] | None, ...], ...] = tuple(
            (None,) * len(gate.inputs) for gate in self.gates
        )
        self._load_inputs()

    def _load_inputs(self) -> None:
        r"""Drive every input wiring with the bits read from stdin."""
        for row in range(self.grid.height):
            line = self.grid.rows[row]
            stripped = line.lstrip()
            if not stripped.startswith("-"):
                continue
            col = len(line) - len(stripped)
            wiring = self._wiring_at((row, col))
            # A row opening on "-" always.
            # wirings are built from those.
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
        r"""Return the wiring covering ``cell``, if any."""
        for wiring in self.wirings:
            if cell in wiring.cells:
                return wiring
        # The machine only looks up.
        # place, so the miss is a guard.
        return None  # pragma: no cover - every cell asked for is covered

    def _read_bit(self) -> int:
        r"""Read one bit of input, taking exhausted input as a zero bit."""
        try:
            value = self.io.input_str()
        except (EOFError, IndexError):
            return 0
        return 1 if value.strip() == "1" else 0

    # The VM's language-shaped view.

    @property
    def ip(self) -> None:
        r"""Always ``None``: nothing moves through a Circuit Diagram."""
        return None

    # : Never a place in the.
    ip_shape = "opaque"

    @property
    def memory(self) -> list[int]:
        r"""The bits driven this generation, in wiring order."""
        return [bit for value in self.values if value is not None for bit in value]

    @property
    def stack(self) -> list[object]:
        r"""Circuit Diagram has no stack."""
        return []

    def step(self) -> None:
        r"""Advance one generation: latch arrivals, fire, then re-drive wires."""
        for text in _emitted((self.values, self.latches), self.wirings, self.gates):
            self.io.print_str(text)
        (self.values, self.latches), halted = _generation(
            (self.values, self.latches), self.wirings, self.gates
        )
        if halted:
            self.halted = True

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the machine's state, hashable for cycle detection."""
        # The two halves of the state.
        # which is what freezing them.
        return (self.values, self.latches, self.halted)


def run(code: list[str], io: IO) -> None:
    r"""Execute a Circuit Diagram program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.readlines(), IO())
