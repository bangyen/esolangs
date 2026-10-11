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
A leading ``-`` reads input ("at the beginning of a line", read past
any indentation) and ``:`` prints the wire to its left.

A *wiring* is a group of wires connected without passing a gate and
holds one value (Null, 0, 1, or a tuple).  Wires connect only when they
point at each other ("connected both ways"), so ``-|`` and ``.|`` are
non-connections; ``.`` connects to all eight neighbours; ``=`` is a
crossover that chains (the prime tester's ``.===.``).

Choices checked against the page's 4-bit prime tester over all sixteen inputs:

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
* **Input format**: consecutive ``0``/``1`` characters, ignoring whitespace.
* **Gate ports are direction-sets.**  The prime tester feeds ``<`` from
  the upper-left ``/`` on one line and the lower-left ``\`` on another,
  so a gate accepts any of its three left neighbours and drives any of
  its three right ones, under the spec's rule that **one wiring may not
  touch both a gate's inputs and its output**.  ``<`` drives only its two
  right diagonals ("from the upper right or lower right"), ``~`` takes
  the level cell when other wirings pass diagonally. One wiring may feed
  both slots of a gate (the constant-output circuit), so ports count per cell.

The page's prime tester omits five characters: two OR inputs are undriven.
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

External bits are consecutive 0/1 characters, ignoring whitespace;
the spec leaves stdin framing unspecified.
"""

from datetime import UTC, datetime
from functools import lru_cache
from typing import cast

from esolangs._drive import drive
from esolangs.interpreters.grid_based.circuit_diagram._functions import (
    _ClockStream,
    _evaluate_function,
)
from esolangs.interpreters.grid_based.circuit_diagram._parse import (
    _CLOCK,
    _COMBINE,
    _ONE,
    _OUTPUT,
    _REMOVE,
    _SPLIT,
    _ZERO,
    _Gate,
    _Grid,
    _LogicGate,
    _Parser,
    _split_definitions,
    _Wiring,
)
from esolangs.interpreters.io import IO


@lru_cache(maxsize=16)
def _compile(
    code: tuple[str, ...],
) -> tuple[
    _Grid,
    list[_Wiring],
    list[_Gate],
    dict[int, int],
    dict[tuple[int, int], _Wiring],
    tuple[tuple[tuple[int, int], ...], ...],
]:
    """Return the validated, read-only topology shared by public runs.

    The last part lists, per wiring, the ``(gate, slot)`` pairs it feeds,
    so a generation visits only the gates downstream of a live wire.
    """
    main, definitions = _split_definitions(list(code))
    grid = _Grid(main)
    parsed = _Parser(grid, definitions)
    wirings = parsed.wirings
    index = {id(wiring): i for i, wiring in enumerate(wirings)}
    fed: list[list[tuple[int, int]]] = [[] for _ in wirings]
    for position, gate in enumerate(parsed.gates):
        if gate.kind not in (_OUTPUT, _ZERO, _ONE, _CLOCK):
            for slot, wiring in enumerate(gate.inputs):
                fed[index[id(wiring)]].append((position, slot))
    return (
        grid,
        wirings,
        parsed.gates,
        index,
        {cell: wiring for wiring in wirings for cell in wiring.cells},
        tuple(map(tuple, fed)),
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
    gate: "_Gate", inputs: list[tuple[int, ...]], clock: _ClockStream | None = None
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
        return [(gate.outputs[0], _evaluate_function(gate, tuple(inputs), clock))]
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


def _emitted(state: _State, gates: list["_Gate"], index: dict[int, int]) -> list[str]:
    """Return what each ``:`` gate writes this generation, in gate order."""
    values, _ = state
    out = []
    for gate in gates:
        if gate.kind != _OUTPUT:
            continue
        value = values[index[id(gate.inputs[0])]]
        if value is not None:
            out.append("".join(str(bit) for bit in value))
    return out


def _generation(
    state: _State,
    gates: list["_Gate"],
    index: dict[int, int],
    consumers: tuple[tuple[tuple[int, int], ...], ...],
    clock: _ClockStream | None = None,
) -> tuple[_State, bool]:
    """Return the state after one generation, and whether the run went quiet.

    Latch arrivals, fire every gate whose slots are full, re-drive every
    wiring; a wiring nothing drove goes Null again.
    """
    values, latches = state
    arrivals: dict[int, list[tuple[int, ...] | None]] = {}
    for wire, value in enumerate(values):
        if value is not None:
            for position, slot in consumers[wire]:
                slots = arrivals.setdefault(position, list(latches[position]))
                slots[slot] = value
    pending: dict[int, list[tuple[int, ...]]] = {}
    fired = False
    grown = list(latches)
    # Gate order, as before: clock reads and merges depend on it.
    for position in sorted(arrivals):
        slots = arrivals[position]
        grown[position] = tuple(slots)
        if any(slot is None for slot in slots):
            continue
        fired = True
        inputs = [slot for slot in slots if slot is not None]
        for wiring, value in _drive(gates[position], inputs, clock):
            pending.setdefault(index[id(wiring)], []).append(value)

    quiet = not fired and all(value is None for value in values)
    driven: list[tuple[int, ...] | None] = [None] * len(values)
    for i, arrived in pending.items():
        driven[i] = _merge(arrived)
    return (tuple(driven), tuple(grown)), quiet


class _Machine:
    """Per-run Circuit Diagram state: the wirings, the gates, their latches.

    Values are events (see the module docstring); ``halted`` is true once
    a generation is quiescent.  Latches are part of :meth:`snapshot`.
    """

    #: Whether a read past the end of the input yields a *value* here
    #: rather than raising.  A few languages do; the rest raise
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

    def __init__(
        self, code: list[str], io: IO, *, clock: _ClockStream | None = None
    ) -> None:
        """Parse ``code`` and read the input its ``-n-`` ports call for."""
        self.clock = clock if clock is not None else _ClockStream()
        self.io = io
        (
            self.grid,
            self.wirings,
            self.gates,
            self.index,
            self._by_cell,
            self.consumers,
        ) = _compile(tuple(code))
        self.halted = False
        # Static topology is shared; values and remembered gate inputs stay
        # per-machine tuples indexed by topology position.
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
        machine.clock = _ClockStream()
        machine.io = io
        (
            machine.grid,
            machine.wirings,
            machine.gates,
            machine.index,
            machine._by_cell,  # noqa: SLF001 -- alternate constructor
            machine.consumers,
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
            # Every leading dash belongs to a wiring. Connected input rows
            # still consume separate bundles before their drivers are XORed.
            if wiring is None:  # pragma: no cover - see above
                continue
            position = self.index[id(wiring)]
            value = tuple(self._read_bit() for _ in range(wiring.width))
            old = self.values[position]
            driven = [value] if old is None else [old, value]
            self.values = (
                *self.values[:position],
                _merge(driven),
                *self.values[position + 1 :],
            )

    def _wiring_at(self, cell: tuple[int, int]) -> _Wiring | None:
        """Return the wiring covering ``cell``, if any."""
        return self._by_cell.get(cell)

    def _read_bit(self) -> int:
        """Read one bit of input, taking exhausted input as a zero bit."""
        try:
            value = self.io.input_bit()
        except (EOFError, IndexError):
            return 0
        return value

    def _load_sources(self) -> None:
        """Drive constants and the clock in generation zero."""
        seconds = (
            self.clock.read() if any(gate.kind == _CLOCK for gate in self.gates) else 0
        )
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

    def step(self) -> None:
        """Advance one generation: latch arrivals, fire, then re-drive wires.

        Every ``:`` gate whose wire carries a value prints, in gate order.
        """
        for text in _emitted((self.values, self.latches), self.gates, self.index):
            self.io.print_str(text)
        (self.values, self.latches), halted = _generation(
            (self.values, self.latches),
            self.gates,
            self.index,
            self.consumers,
            self.clock,
        )
        if halted:
            self.halted = True

    def snapshot(self) -> tuple[object, ...]:
        """Return events, latches, halt and the runtime clock-read cursor."""
        # The two halves of the state are already the tuples this wants,
        # which is what freezing them bought: no per-call rebuild.
        return (self.values, self.latches, self.halted, self.clock.position)


def run(code: list[str], io: IO) -> None:
    """Execute a Circuit Diagram program."""
    machine = _Machine._for_run(code, io)  # noqa: SLF001 -- public fast path
    drive(machine)
