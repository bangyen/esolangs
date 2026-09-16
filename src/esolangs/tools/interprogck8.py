"""Boolean-function generator for Interprogck8.

Routing rides a *shared corridor* instead of a private router: every odd
line nothing occupies is a bare ``DownAccLines`` rung, and a rung is
stateless, so one lattice serves every chain at once.  ``u`` reads the
digit and two ``@dd`` leave 28 or 29 in the accumulator, and from an odd
rung the stride ``1 + acc`` preserves line parity exactly when the bit
was 1 -- so a 0 dismounts onto one even line 29 below the launch rung,
while a 1 flies odd lines of one residue class mod 30 until the first
non-rung line on that class, the node's *stop*.  Which line catches a
chain is arithmetic in (position, stride); no chain owns a rung.  That
is what removes the old router's super-linear term: it paid ~span/255
private rungs per express chain and every tree level cost the same
``L/255`` again, where the corridor is paid once for everyone.
Measured: per-entry cost oscillates between 805 and 887 characters over
n=8..12 with no trend (the old router climbed 328 to 526 over n=3..10),
and the registry scaling contract reads x1.963 against its x2.15 bound
with no exemption.

Interference is phase separation.  Each read depth owns a channel -- a
(stride, residue) pair -- and every odd-line instruction avoids every
channel that crosses it, so a flight passes any number of deeper
subtrees without dismounting.  A stride class holds 14 residues, handed
out descending so the read's own adjuster lines fall on residues no
channel uses; deeper depths append ``@nd`` adjusters, so class ``k``
flies stride ``30 + 2k`` and opens 14 fresh residues.  Class 113 is the
last (a stride is one accumulator step, at most 256), 1596 read depths
-- no representable table reaches that, so the construction is total
over its inputs.  A constant subtree folds to a *consume* chain: one
read per remaining input whose both arms converge, by flow, on the next
-- the 0-arm's zeroed flow walks forward through the 1-arm's stop.
Leaf arms load 65 with one ``nNnN`` and fly stride 66 to the nearest of
four shared printer stops per digit; the print code is sequential text
past the stops, where nothing flies.

Assembly is one forward pass over computed coordinates -- no width
fixed point, no meadows, no repair rounds -- dense n=9 builds in ~0.04s
against the old router's minutes-scale repairs.  Every flight is
checked after it: :func:`_validate` walks the emitted lines exactly as
``DownAccLines`` flies them, and a flight that would dismount anywhere
but its stop is refused rather than emitted.
"""

from esolangs.tools.helpers import _validate_truth_table

#: The corridor line.  ``DownAccLines`` jumps to ``ip + 1 + acc`` and
#: leaves the accumulator alone, which is the whole sharing argument.
_RUNG = "DownAccLines"

#: Stride a 1-bit flies at with no class adjusters: ``u`` then two
#: ``@dd`` leave 29, and a rung adds one.  Each class adds two.
_BASE_STRIDE = 30

#: Residues a stride class hands out: the top 14 odd residues,
#: descending with depth.  The reserve below them is load-bearing: a
#: class-``k`` read trails ``2 + 2k`` adjusters whose ``1 + k`` odd
#: lines sit on the residues just below its own phase, and descending
#: from ``stride - 1`` spills them exactly down to residue 1 -- never
#: onto a residue any channel owns.
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


def _channel(depth: int) -> tuple[int, int]:
    """Return the (stride, launch residue) pair depth ``depth`` owns."""
    group, index = divmod(depth, _PHASES_PER_CLASS)
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

        Only odd lines can sit on a channel: flights land on odd lines
        alone, so an even line never needs the residue check.
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

        The line must meet ``parity`` and every congruence, and all of
        ``line .. line + span - 1`` must clear ``avoid`` -- a read's
        adjusters trail it, so the footprint is checked as one piece.
        The scan bound is a backstop against a planning bug, not a
        budget: a free line on any single congruence class recurs
        within its modulus times the longest occupied run.
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

        Every printer flight flies from its leaf to a stop at the end of
        the program, so laid one by one they walked the whole text once
        per leaf: 8.6 million rung visits for a 395 thousand line program
        at twelve inputs, Theta(T^2) for a linear output, x3.3 per added
        input.  Flights on one channel -- same stride, same residue, same
        stop -- lay the same rungs, and the earliest launch's walk covers
        every later one's range, so the channel is walked from its
        earliest launch exactly once.  The lines touched, the order they
        are touched in, and the collision checks are the same as the
        one-by-one walks made; only the repeats are gone.  Each flight
        is still recorded for :func:`_validate`.
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


def _assemble(table: str, n: int) -> tuple[list[str], list[_Flight]]:
    """Lay the whole program out; every coordinate is final when written."""
    layout = _Layout()
    printer_flights: list[tuple[int, int]] = []

    def launch_pad(entry: int, value: int) -> int:
        """Place a printer launch, reached by acc-0 flow from ``entry``.

        One even line loading 65; the rung after it flies stride 66 on
        whichever of the digit's four residues is nearest, so the pad
        costs a few lines of slack rather than half a period.
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
        """Place one read and its adjusters; return (launch, stride, arm).

        ``launch`` is the rung both arms leave from, ``arm`` the even
        line the 0-arm dismounts onto.  The footprint -- the read, four
        ``@dd``, the class's ``@nd`` tail -- is placed as one piece so
        its odd lines stay off every crossing channel.
        """
        stride, phase = _channel(depth)
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

    def node(lo: int, hi: int, depth: int, entry: int, open_channels: _Avoid) -> int:
        """One subtree: place it, return the frontier line."""
        if depth == n:
            return launch_pad(entry, int(table[lo])) + 2
        window = table[lo:hi]
        if len(set(window)) == 1:
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
        below = (*open_channels, (stride, frozenset({launch % stride})))
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

    The corridor's one failure mode is a non-rung line straying onto an
    open channel, which would dismount a chain mid-flight and compute
    the wrong row -- so a program is emitted only after every flight
    has been walked to its intended stop on the emitted text.

    A walk is shared where flights share a channel and a stop.  A flight
    whose launch is a rung lying on the path an already-walked flight
    took to the same stop flies that walk's suffix, so it dismounts where
    that walk did; the walk it would make is the tail of one already
    made on this text.  Each channel is therefore walked from its
    earliest launch once rather than once per leaf, which is what kept
    this linear once the printer flights were laid the same way.
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
