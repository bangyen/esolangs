"""Boolean-function generator for Interprogck8.

Routing rides a *shared corridor*: every unoccupied odd line is a
stateless ``DownAccLines`` rung, so one lattice serves every chain.
``u`` reads the digit and two ``@dd`` leave 28 or 29 in the accumulator;
from an odd rung the stride ``1 + acc`` preserves line parity exactly
when the bit was 1, so a 0 dismounts onto one even line 29 below and a 1
flies odd lines of one residue class mod 30 to the first non-rung line
on that class, the node's *stop*.  The old router paid ~span/255 private
rungs per express chain and ``L/255`` again per level; the corridor is
paid once.

Each read depth owns a (stride, residue) channel and every odd-line
instruction avoids every channel crossing it, so a flight passes deeper
subtrees without dismounting.  A stride class holds up to 14 residues
handed out descending; class ``k`` flies stride ``30 + 2k`` with ``2k``
``@nd`` adjusters.  Size is O(T) at every arity -- each gadget is a
fixed span for its class and a placement scan ends within a bounded
distance -- but the constant is a step function of the arity, not a
line: through fourteen inputs every read is class 0 and three lines,
805-887 characters per entry over n=8..12 with no trend, and the
scaling contract's x1.963 reads that flatness, which is the class
boundary and not evidence of anything past it.  From fifteen inputs
:func:`_phases` thins the pool so a second class fits under the first,
and the sparser placements cost 6300-6600 characters per entry at
n=15; forty inputs is the last the probe places (the old text claimed
1596 read depths, but a class-``k`` read's ``1 + k`` odd lines need
``1 + k`` free consecutive residues in every class below it, which a
full class never leaves).  A constant subtree folds to a *consume*
chain whose arms converge by flow.  Leaf arms load 65 with one
``nNnN`` and fly stride 66 to the nearest of four shared printer stops
per digit.

Assembly is one forward pass over computed coordinates: dense n=9 builds
in ~0.04s against the old router's minutes of repairs.
:func:`_validate` walks every emitted flight as ``DownAccLines`` would
and refuses one that dismounts anywhere but its stop.
"""

from itertools import pairwise

from esolangs.exceptions import TruthTableError
from esolangs.tools.helpers import _validate_truth_table

#: The corridor line.  ``DownAccLines`` jumps to ``ip + 1 + acc`` and
#: leaves the accumulator alone, which is the whole sharing argument.
_RUNG = "DownAccLines"

#: Stride a 1-bit flies at with no class adjusters: ``u`` then two
#: ``@dd`` leave 29, and a rung adds one.  Each class adds two.
_BASE_STRIDE = 30

#: The most residues a stride class hands out: the top 14 odd residues
#: mod 30, descending with depth.  The reserve below them is
#: load-bearing: a class-``k`` read trails ``2 + 2k`` adjusters whose
#: ``1 + k`` odd lines sit on the residues just below its own phase, and
#: descending from ``stride - 1`` spills them exactly down to residue 1
#: -- never onto a residue any channel owns.  The same ``1 + k`` odd
#: lines must also clear every shallower class in the air, so a class
#: past the first needs the classes below it to leave residues *unused*:
#: :func:`_phases` hands out fewer per class as the tree deepens.
_PHASES_PER_CLASS = 14

#: Stride a leaf arm flies at: ``nNnN`` loads 65 in one line.
_PRINT_STRIDE = 66

#: The printer channels' residues mod 66, four per output digit so a
#: leaf arm reaches the nearest one cheaply.  Each digit's four are
#: clustered (spacing four, never two: a leaf 1-arm's stop sits two
#: lines before its launch rung, and two below a live residue that
#: stop would be dismounted on by other flights), and the 0 cluster is
#: kept narrow so the 1-printer's sequential code block -- which the
#: 0 flights cross -- fits between two of its passes.
_PRINT_PHASE = {0: (33, 37, 41, 45), 1: (1, 5, 9, 13)}


def _channel(depth: int, phases: int) -> tuple[int, int]:
    """Return the (stride, launch residue) pair depth ``depth`` owns."""
    group, index = divmod(depth, phases)
    stride = _BASE_STRIDE + 2 * group
    return stride, stride - 1 - 2 * index


#: One flight: its launch rung, its stride, and the stop that must catch
#: it.  Kept for :func:`_validate` to walk against the emitted text.
type _Flight = tuple[int, int, int]

#: Channels a placement must stay off: ``(modulus, forbidden residues)``.
type _Avoid = tuple[tuple[int, frozenset[int]], ...]

_PRINTER_CHANNELS: _Avoid = (
    (_PRINT_STRIDE, frozenset(_PRINT_PHASE[0] + _PRINT_PHASE[1])),
)


def _opened(channels: _Avoid, stride: int, residue: int) -> _Avoid:
    """``channels`` with one more residue open on ``stride``.

    One entry per modulus, so a clear check costs the number of stride
    classes in the air (one below depth 14) rather than the number of
    open flights, which is the depth.
    """
    for i, (mod, bad) in enumerate(channels):
        if mod == stride:
            return (*channels[:i], (mod, bad | {residue}), *channels[i + 1 :])
    return (*channels, (stride, frozenset({residue})))


class _Layout:
    """The assembly state: placed lines, laid rungs, recorded flights."""

    def __init__(self) -> None:
        self.ops: dict[int, str] = {}
        self.flights: list[_Flight] = []

    def put(self, line: int, op: str) -> None:
        """Occupy ``line`` with ``op``; a collision is a planning bug."""
        if line in self.ops:
            raise AssertionError(f"line {line} holds {self.ops[line]!r}, wanted {op!r}")
        self.ops[line] = op

    def put_rung(self, line: int) -> None:
        """Lay one corridor rung; sharing an existing rung is the point."""
        if line % 2 == 0:
            raise AssertionError(f"rung on even line {line}")
        existing = self.ops.setdefault(line, _RUNG)
        if existing != _RUNG:
            raise AssertionError(f"rung vs {existing!r} at line {line}")

    def clear(self, line: int, avoid: _Avoid) -> bool:
        """Whether ``line`` is free and off every channel in ``avoid``.

        Only odd lines can sit on a channel.
        """
        if line in self.ops:
            return False
        if line % 2 == 0:
            return True
        return all(line % mod not in bad for mod, bad in avoid)

    def place(
        self,
        start: int,
        parity: int,
        congruences: tuple[tuple[int, int], ...],
        avoid: _Avoid = (),
        span: int = 1,
    ) -> int:
        """First line at or past ``start`` whose whole gadget fits.

        All of ``line .. line + span - 1`` must clear ``avoid``.  The scan
        bound is a backstop, not a budget: a free line on one congruence
        class recurs within its modulus times the longest occupied run.
        """
        line = start
        for _ in range(100_000):
            if (
                line % 2 == parity
                and all(line % mod == residue for mod, residue in congruences)
                and all(self.clear(line + i, avoid) for i in range(span))
            ):
                return line
            line += 1
        raise AssertionError(f"no placement past {start} met {congruences}")

    def lay(self, launch: int, stride: int, stop: int) -> None:
        """Lay one flight's rungs from ``launch`` up to (not on) ``stop``."""
        self._walk(launch, stride, stop)
        self.flights.append((launch, stride, stop))

    def lay_shared(self, flights: list[tuple[int, int, int]]) -> None:
        """Lay flights that share stops, walking each channel once.

        Laid one by one, printer flights walked the whole text once per
        leaf: 8.6 million rung visits for a 395 thousand line program at
        twelve inputs, x3.3 per added input.  Flights on one channel lay
        the same rungs and the earliest launch's walk covers every later
        one, so the checks are the same and only the repeats are gone.
        """
        earliest: dict[tuple[int, int, int], int] = {}
        for launch, stride, stop in flights:
            key = (stride, launch % stride, stop)
            earliest[key] = min(earliest.get(key, launch), launch)
        for (stride, _residue, stop), launch in earliest.items():
            self._walk(launch, stride, stop)
        self.flights.extend(flights)

    def _walk(self, launch: int, stride: int, stop: int) -> None:
        """Put a rung on every line of the flight, checking each."""
        position = launch
        while position != stop:
            if position > stop:
                raise AssertionError(
                    f"flight {launch}+{stride}k steps over its stop {stop}"
                )
            self.put_rung(position)
            position += stride


def _read_gadget(
    layout: _Layout, depth: int, phases: int, entry: int, open_channels: _Avoid
) -> tuple[int, int, int]:
    """Place one read and its adjusters; return (launch, stride, arm).

    ``launch`` is the rung both arms leave from, ``arm`` the even line
    the 0-arm dismounts onto; the footprint is placed as one piece.
    """
    stride, phase = _channel(depth, phases)
    width = stride - 27  # ``u`` + 2 ``@dd`` + (stride - 30) ``@nd``
    read = layout.place(
        entry,
        0,
        ((stride, (phase + 5) % stride),),
        open_channels,
        span=width,
    )
    layout.put(read, "u")
    for offset in range(1, 3):
        layout.put(read + offset, "@dd")
    for offset in range(3, width):
        layout.put(read + offset, "@nd")
    launch = read + width
    return launch, stride, launch + stride - 1


def _phases(n: int) -> int:
    """Residues per stride class for an ``n``-input tree.

    The most, up to :data:`_PHASES_PER_CLASS`, under which every read
    depth below ``n`` places with every shallower flight in the air --
    the leftmost unfolded path, where a depth-``d`` read must clear ``d``
    open channels.  Fourteen serve fourteen inputs on one stride class;
    a fifteenth needs a second class, whose two-odd-line read never fits
    under a full first, and every class past it thins the pool further:
    thirteen reach 26 inputs, twelve 36, nine 40, and none reach 41,
    where the intersecting congruences run past the placement scan.
    Probed here rather than tabulated, on the placer itself.
    """
    for phases in range(_PHASES_PER_CLASS, 0, -1):
        layout = _Layout()
        avoid: _Avoid = _PRINTER_CHANNELS
        entry = 2
        try:
            for depth in range(n):
                launch, stride, arm = _read_gadget(layout, depth, phases, entry, avoid)
                avoid = _opened(avoid, stride, launch % stride)
                entry = arm + 2
        except AssertionError:
            continue
        return phases
    raise TruthTableError(
        f"Interprogck8's corridor routes at most 40 inputs, not {n}: "
        "no residue pool places every read depth under a fully open stack"
    )


def _assemble(table: str, n: int) -> tuple[list[str], list[_Flight]]:
    """Lay the whole program out; every coordinate is final when written."""
    phases = _phases(n)
    layout = _Layout()
    printer_flights: list[tuple[int, int]] = []
    # ``changes[r]`` counts the value changes before row ``r``: a window is
    # constant iff its ends agree, where a slice and a set per node would
    # cost ``Theta(n T)`` over the tree.
    changes = [0]
    for previous, current in pairwise(table):
        changes.append(changes[-1] + (previous != current))

    def launch_pad(entry: int, value: int) -> int:
        """Place a printer launch, reached by acc-0 flow from ``entry``.

        One even line loading 65; the rung after flies stride 66 on the
        nearest of the digit's four residues.
        """
        line = min(
            layout.place(entry, 0, ((_PRINT_STRIDE, (residue - 1) % _PRINT_STRIDE),))
            for residue in _PRINT_PHASE[value]
        )
        layout.put(line, "nNnN")
        printer_flights.append((line + 1, value))
        return line

    def read_gadget(
        depth: int, entry: int, open_channels: _Avoid
    ) -> tuple[int, int, int]:
        return _read_gadget(layout, depth, phases, entry, open_channels)

    def node(lo: int, hi: int, depth: int, entry: int, open_channels: _Avoid) -> int:
        """One subtree: place it, return the frontier line."""
        if depth == n:
            return launch_pad(entry, int(table[lo])) + 2
        if changes[lo] == changes[hi - 1]:
            # A constant subtree folds to a consume chain: the read
            # still happens -- the reads are the interface -- but both
            # arms converge on one child.  The 0-arm's zeroed flow
            # walks forward *through* the 1-arm's stop (a second
            # ``NnNn`` under an already-zero accumulator), so the two
            # arms meet without a join gadget.
            launch, stride, arm = read_gadget(depth, entry, open_channels)
            layout.put(arm, "NnNn")
            stop = layout.place(
                arm + 1,
                1,
                ((stride, launch % stride),),
                (*open_channels, *_PRINTER_CHANNELS),
            )
            layout.put(stop, "NnNn")
            layout.lay(launch, stride, stop)
            return node(lo, hi, depth + 1, stop + 1, open_channels)
        half = (hi - lo) // 2
        launch, stride, arm = read_gadget(depth, entry, open_channels)
        below = _opened(open_channels, stride, launch % stride)
        layout.put(arm, "NnNn")
        frontier = node(lo, lo + half, depth + 1, arm + 2, below)
        stop = layout.place(
            max(frontier, launch + 2),
            1,
            ((stride, launch % stride),),
            (*open_channels, *_PRINTER_CHANNELS),
        )
        layout.put(stop, "NnNn")
        layout.lay(launch, stride, stop)
        return node(lo + half, hi, depth + 1, stop + 2, below)

    end = node(0, len(table), 0, 2, _PRINTER_CHANNELS)

    # The printer region.  Flights for 1 stop first; their code is
    # sequential text (stops and code are contiguous occupied lines, so
    # parity plays no role) ending in one hop over the 0 side to the
    # program end.  Flights for 0 cross that code on their own four
    # residues, which the code block's placement stays off.
    zero_avoid: _Avoid = ((_PRINT_STRIDE, frozenset(_PRINT_PHASE[0])),)
    cursor = end + 2
    one_stops = []
    for residue in _PRINT_PHASE[1]:
        stop = layout.place(cursor, 1, ((_PRINT_STRIDE, residue),), zero_avoid)
        layout.put(stop, "NnNn")
        one_stops.append(stop)
        cursor = stop + 1
    one_code = ["@id"] * 4 + ["@nd"] * 9 + ["div"]
    escape_slack = 26  # ``NnNn`` + the distance spelling + the hop
    code = layout.place(cursor, 0, (), zero_avoid, span=len(one_code) + escape_slack)
    for offset, op in enumerate(one_code):
        layout.put(code + offset, op)
    escape = code + len(one_code)
    cursor = escape + escape_slack
    zero_stops = []
    for residue in _PRINT_PHASE[0]:
        stop = layout.place(cursor, 1, ((_PRINT_STRIDE, residue),))
        layout.put(stop, "NnNn")
        zero_stops.append(stop)
        cursor = stop + 1
    zero_code = ["@id"] * 4 + ["@nd"] * 8 + ["div"]
    for offset, op in enumerate(zero_code):
        layout.put(cursor + offset, op)
    length = cursor + len(zero_code)  # the 0-printer falls off the end
    # The 1-printer's hop over the 0 side: respell and fly to the end.
    distance = length - (escape + escape_slack - 1) - 1
    if distance > 255:
        raise AssertionError(f"printer escape spans {distance} lines")
    spell = ["NnNn"] + ["@id"] * (distance // 10) + ["@nd"] * (distance % 10)
    for offset, op in enumerate(spell):
        layout.put(escape + offset, op)
    for offset in range(len(spell), escape_slack - 1):
        layout.put(escape + offset, "x")
    layout.put(escape + escape_slack - 1, _RUNG)

    shared = []
    for launch, value in printer_flights:
        landing = launch % _PRINT_STRIDE
        stops = one_stops if value else zero_stops
        stop = next(s for s in stops if s % _PRINT_STRIDE == landing)
        shared.append((launch, _PRINT_STRIDE, stop))
    layout.lay_shared(shared)

    lines = [layout.ops.get(i, _RUNG if i % 2 else "x") for i in range(length)]
    return lines, layout.flights


def _validate(lines: list[str], flights: list[_Flight]) -> None:
    """Walk every flight exactly as ``DownAccLines`` would fly it.

    A non-rung line straying onto an open channel would dismount a chain
    mid-flight, so every flight is walked to its stop on the emitted text.
    A flight launching from a rung on an already-walked path to the same
    stop flies that walk's suffix, so each channel is walked once from its
    earliest launch, which keeps this linear.
    """
    reached: dict[tuple[int, int, int], int] = {}
    for launch, stride, stop in flights:
        if lines[launch] != _RUNG:
            raise AssertionError(f"launch {launch} is {lines[launch]!r}")
        key = (stride, launch % stride, stop)
        known = reached.get(key)
        if known is not None and known <= launch < stop:
            continue  # on a walked path to this stop: its suffix
        position = launch + stride
        while lines[position] == _RUNG and position != known:
            position += stride
            if position >= len(lines):
                raise AssertionError(f"flight from {launch} overshot the end")
        if position != stop and position != known:
            raise AssertionError(
                f"flight from {launch} at stride {stride} dismounts on "
                f"{lines[position]!r} at {position}, not its stop {stop}"
            )
        reached[key] = launch


def interprogck8(truth_table: str) -> str:
    """Return a program printing ``truth_table``'s result for its inputs.

    Reads ``n`` digits, one per line, and prints ``0`` or ``1``.
    """
    n = _validate_truth_table(truth_table)
    lines, flights = _assemble(truth_table, n)
    _validate(lines, flights)
    return "\n".join(lines)
