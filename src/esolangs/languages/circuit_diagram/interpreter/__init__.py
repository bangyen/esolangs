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

Named ``{function ... }`` blocks are removed from the main grid and called
as atomic custom gates.  Their input rows bind symbolic widths at each call;
their output ports are concatenated into the call's output multi-wire.

Input/output:
    External bits are consecutive 0/1 characters, ignoring whitespace; the
    spec leaves stdin framing unspecified.  At EOF a read yields a **zero
    bit** rather than raising, since every gate is live at once and the
    automaton needs a value to settle on; no :class:`HaltError` is raised.

Errors:
    ProgramError: An unknown or out-of-scope character; an unknown function
    or wire label; a wire label that annotates no wire or is not positive;
    inconsistent or unsettled wire widths; a gate with the wrong input or
    output count; a wiring feeding and fed by one gate; ``:`` without ``-``
    directly to its left; a split of a one-wire bundle; ``%`` removing every
    wire; a function block that is unterminated, unmatched, duplicated or
    reserved; a function call with a wrong input width or label, that
    recurses, does not settle, or returns no bits.

Decisions:
    Checked against the page's 4-bit prime tester over all sixteen inputs.

    * **Values are events, and gates latch them.**  Sticky wirings are
      falsified by the page's flip-flop, which outputs ``1N1N1N...``; so a
      value lasts one generation (XOR of what fired into it, else Null).
      Per "the gate waits until the other input comes", each gate keeps a
      latch per input slot, overwritten by each non-null arrival, and fires
      when every slot is filled *and* one input is live (a non-null value
      arrives this generation, even one equal to its latch) -- which stops a
      filled latch re-firing forever.  ``:`` prints in every generation its
      wire carries a value, changed or not; a program halts on a quiescent
      generation.  A feedback circuit (the flip-flop is period 2) never
      halts: a plain run prints until killed, and
      :func:`esolangs.vm.run_until_halt_or_cycle` stops it at the first
      repeated state, having printed all along (the flip-flop's ``:``
      printed ``111``).  Latches are part of the machine's snapshot.
    * **Wire 1 is the first bit read and the MSB**: the only ordering under
      which the example's formula is primality.  A multi-wire is a tuple in
      that order, so ``<`` gives its first ``n // 2`` wires to the upper
      output and the rest to the lower, and ``>`` puts its upper input first.
    * **Gate ports are direction-sets.**  The prime tester feeds ``<`` from
      the upper-left ``/`` on one line and the lower-left ``\`` on another,
      so a gate takes inputs from its three left neighbours and drives its
      three right ones, the count found being exactly its arity (more or
      fewer is a ProgramError), under the spec's rule that **one wiring may
      not touch both a gate's inputs and its output**.  ``<`` drives only its
      two right diagonals ("from the upper right or lower right"), ``~``
      takes only the level cell as its input when other wirings pass
      diagonally (outputs have no such rule).  One wiring may feed both
      slots of a gate (the constant-output circuit), so ports count per
      cell.
    * The page's prime tester omits five characters: two OR inputs are
      undriven.  The repair is derived and unique: the circuit is a product
      of sums ``(? | c)``, ``(? | ~a | ~b)``, ``(d | ~a)``, ``(~b | d)``;
      primality over 0-15 with ``a`` the MSB forces the unknowns to ``~c``
      (inputs 13 and 15) and ``b`` (inputs 0, 1, 9).  The page already
      draws the ``=`` crossovers where ``~c``'s diagonal would cross and
      omits only the ``/`` between them; ``b``'s horizontal run stops four
      columns short.
"""

from collections import OrderedDict
from datetime import UTC, datetime
from threading import Lock
from typing import NamedTuple, cast

from esolangs.languages.circuit_diagram.interpreter._functions import (
    _BufferedClock,
    _ClockNeededError,
    _ClockStream,
    _evaluate_function,
)
from esolangs.languages.circuit_diagram.interpreter._parse import (
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
from esolangs.runtime._drive import drive
from esolangs.runtime.io import IO

# ``tests/test_circuit_diagram.py`` carries ``PRIME_TESTER`` (repaired, replayed over
# sixteen inputs) and ``PRIME_TESTER_AS_DRAWN`` (silence pinned).


class _Topology(NamedTuple):
    """The validated, read-only diagram shared by public runs.

    ``wire_index`` maps ``id(wiring)`` to its position; ``consumers`` lists, per
    wiring, the ``(gate, slot)`` pairs it feeds, so a generation visits only
    the gates downstream of a live wire.
    """

    grid: _Grid
    wirings: list[_Wiring]
    gates: list[_Gate]
    wire_index: dict[int, int]
    by_cell: dict[tuple[int, int], _Wiring]
    consumers: tuple[tuple[tuple[int, int], ...], ...]


def _parse_topology(code: tuple[str, ...]) -> _Topology:
    """Return the :class:`_Topology` of ``code``."""
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
    return _Topology(
        grid,
        wirings,
        parsed.gates,
        index,
        {cell: wiring for wiring in wirings for cell in wiring.cells},
        tuple(map(tuple, fed)),
    )


#: How much program text the compile cache retains, in characters, across
#: all of its entries and in any single one.
_MAX_CACHED_TEXT = 16_000_000

#: How many programs the compile cache retains at once.
_MAX_CACHED_PROGRAMS = 16


class _CacheInfo(NamedTuple):
    """The compile cache's counters, shaped like ``functools``' own."""

    hits: int
    misses: int
    maxsize: int | None
    currsize: int


class _CompileCache:
    """An LRU over :func:`_parse_topology`, bounded by retained text.

    A plain ``functools.lru_cache(maxsize=16)`` bounds only the entry
    count, so sixteen topologies of generated programs stay alive for the
    rest of the process -- one measured program is 30M characters of code
    and about a gigabyte of topology -- and whichever later compile is
    first to evict one pays for freeing it (1.04 s of CPU measured for
    that program, charged to a test whose own work is a millisecond).
    Bounding the retained *text* instead caps what any single eviction
    can cost, and a program past the bound is parsed per machine rather
    than retained at all: the programs that large are built by the slow
    and weekly executions, which run a handful of rows each and can pay
    their own parses.
    """

    def __init__(self) -> None:
        """Start an empty cache over :func:`_parse_topology`."""
        self.__wrapped__ = _parse_topology
        self._entries: OrderedDict[tuple[str, ...], tuple[_Topology, int]] = (
            OrderedDict()
        )
        self._text = 0
        self._hits = 0
        self._misses = 0
        self._lock = Lock()

    def __call__(self, code: tuple[str, ...]) -> _Topology:
        """Return ``code``'s topology, parsing and maybe retaining it."""
        with self._lock:
            entry = self._entries.pop(code, None)
            if entry is not None:
                self._entries[code] = entry
                self._hits += 1
                return entry[0]
            self._misses += 1
        topology = _parse_topology(code)
        size = sum(map(len, code))
        if size <= _MAX_CACHED_TEXT:
            with self._lock:
                replaced = self._entries.pop(code, None)
                if replaced is not None:
                    self._text -= replaced[1]
                self._entries[code] = (topology, size)
                self._text += size
                while (
                    len(self._entries) > _MAX_CACHED_PROGRAMS
                    or self._text > _MAX_CACHED_TEXT
                ):
                    _, (_, evicted) = self._entries.popitem(last=False)
                    self._text -= evicted
        return topology

    def cache_info(self) -> _CacheInfo:
        """Return the hit/miss counters and the current entry count."""
        with self._lock:
            return _CacheInfo(
                self._hits, self._misses, _MAX_CACHED_PROGRAMS, len(self._entries)
            )

    def cache_clear(self) -> None:
        """Drop every retained topology and reset the counters."""
        with self._lock:
            self._entries.clear()
            self._text = 0
            self._hits = 0
            self._misses = 0


#: The shared compile cache every machine in this process runs through.
_compile = _CompileCache()


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


def _emitted(values: _Values, topology: _Topology) -> list[str]:
    """Return what each ``:`` gate writes this generation, in gate order."""
    out = []
    for gate in topology.gates:
        if gate.kind != _OUTPUT:
            continue
        value = values[topology.wire_index[id(gate.inputs[0])]]
        if value is not None:
            out.append("".join(str(bit) for bit in value))
    return out


def _latch_arrivals(
    values: _Values,
    latches: _Latches,
    topology: _Topology,
) -> tuple[dict[int, list[tuple[int, ...] | None]], _Latches]:
    """Record this generation's arrivals in each downstream gate's latch slots.

    Returns the per-gate slot lists (only for gates with arrivals) and the
    full updated latch tuples.
    """
    arrivals: dict[int, list[tuple[int, ...] | None]] = {}
    for wire, value in enumerate(values):
        if value is not None:
            for position, slot in topology.consumers[wire]:
                slots = arrivals.setdefault(position, list(latches[position]))
                slots[slot] = value
    grown = tuple(
        tuple(arrivals[position]) if position in arrivals else latches[position]
        for position in range(len(latches))
    )
    return arrivals, grown


def _generation(
    state: _State, topology: _Topology, clock: "_ClockStream"
) -> tuple[_State, bool]:
    """Return the state after one generation, and whether the run went quiet.

    Pure.  The topology is a constant of the run and every clock read is
    served from the source the caller owns (the shell samples it; a
    generation that needs one more raises :class:`_ClockNeededError`, so
    wall time is never read here).  The state handed in is never edited.
    """
    values, latches = state
    arrivals, grown = _latch_arrivals(values, latches, topology)
    pending: dict[int, list[tuple[int, ...]]] = {}
    fired = False
    # Gate order, as before: clock reads and merges depend on it.
    for position in sorted(arrivals):
        slots = arrivals[position]
        if any(slot is None for slot in slots):
            continue
        fired = True
        inputs = [slot for slot in slots if slot is not None]
        for wiring, value in _drive(topology.gates[position], inputs, clock):
            pending.setdefault(topology.wire_index[id(wiring)], []).append(value)

    quiet = not fired and all(value is None for value in values)
    driven: list[tuple[int, ...] | None] = [None] * len(values)
    for i, arrived in pending.items():
        driven[i] = _merge(arrived)
    return (tuple(driven), grown), quiet


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
        self.topology = _compile(tuple(code))
        self.halted = False
        # Static topology is shared; values and remembered gate inputs stay
        # per-machine tuples indexed by topology position.
        self.values: tuple[tuple[int, ...] | None, ...] = (None,) * len(self.wirings)
        self.latches: tuple[tuple[tuple[int, ...] | None, ...], ...] = tuple(
            (None,) * len(gate.inputs) for gate in self.gates
        )
        self._load_inputs()
        self._load_sources()

    # Read-only views of the shared topology.

    @property
    def grid(self) -> _Grid:
        """The parsed diagram grid."""
        return self.topology.grid

    @property
    def wirings(self) -> list[_Wiring]:
        """Every wiring, by position."""
        return self.topology.wirings

    @property
    def gates(self) -> list[_Gate]:
        """Every gate, by position."""
        return self.topology.gates

    @property
    def index(self) -> dict[int, int]:
        """``id(wiring)`` to its position."""
        return self.topology.wire_index

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
            wiring = self.topology.by_cell.get((row, col))
            # Every leading dash belongs to a wiring. Connected input rows
            # still consume separate bundles before their drivers are XORed.
            if wiring is None:  # pragma: no cover - see above
                continue
            position = self.index[id(wiring)]
            value = tuple(self._read_bit() for _ in range(wiring.width))
            self._drive_wiring(position, value)

    def _drive_wiring(self, position: int, value: tuple[int, ...]) -> None:
        """XOR ``value`` into the wiring at ``position``.

        Several drivers may reach one wiring in generation zero (connected
        input rows, a source sharing a driven wire); their bundles merge.
        """
        old = self.values[position]
        driven = [value] if old is None else [old, value]
        self.values = (
            *self.values[:position],
            _merge(driven),
            *self.values[position + 1 :],
        )

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
            self._drive_wiring(position, value)

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

    def _generate(self, clock: _ClockStream) -> bool:
        """Advance one generation through the worker transition.

        Nested function evaluation runs here rather than through
        :meth:`step`, so the clock is the explicit value source the caller
        passes and the shell's wall clock is never touched.
        """
        (self.values, self.latches), halted = _generation(
            (self.values, self.latches), self.topology, clock
        )
        if halted:
            self.halted = True
        return halted

    def step(self) -> None:
        """Advance one generation: latch arrivals, fire, then re-drive wires.

        The shell: every ``:`` gate whose wire carries a value prints, in
        gate order.  The clock is read here, one value per read the
        transition asks for; the transition itself never touches wall time.
        """
        for text in _emitted(self.values, self.topology):
            self.io.print_str(text)
        sampled: list[int] = []
        while True:
            try:
                self._generate(_BufferedClock(tuple(sampled)))
                break
            except _ClockNeededError:
                sampled.append(self.clock.read())

    def snapshot(self) -> tuple[object, ...]:
        """Return events, latches, halt and the runtime clock-read cursor."""
        # The two halves of the state are already the tuples this wants,
        # which is what freezing them bought: no per-call rebuild.
        return (self.values, self.latches, self.halted, self.clock.position)


def run(code: list[str], io: IO) -> None:
    """Execute a Circuit Diagram program."""
    machine = _Machine(code, io)
    drive(machine)
