"""Boolean-function generator for Interprogck8.

The decision tree is routed entirely by ``DownAccLines``, the computed
forward jump.  Nothing here touches the current-function slot: the
roadmap's question was whether a tree had to be squeezed through that
single slot, and it does not have to go near it.

**The branch gadget.**  ``u`` reads the input digit as 48 or 49; ``@dd``
four times and ``@nt`` eight times leave the bit itself in the
accumulator.  ``DownAccLines`` lands on ``ip + 1 + acc``, so the two
values land one line apart -- too close to separate two arms.  A second
jump spreads them:

    DownAccLines      p     bit 0 -> p+1, bit 1 -> p+2
    @id               p+1   bit-0 path only: acc 0 -> 10
    DownAccLines      p+2   bit 1 arrives with 1, bit 0 with 10

so bit 1 lands at ``p+4`` and bit 0 at ``p+13``, nine lines apart.  Past
the split the accumulator is a known constant on each path, so every later
jump is unconditional: ``NnNn`` plus modifiers plus ``DownAccLines`` reaches
any line up to 255 ahead, and further by riding the express (below).

**Layout.**  Both landing sites hold jumps rather than code, so neither arm
has to be spelled inside the nine-line window: the window hops to a relay
just past the bit-0 jump, and the relay enters the bit-1 subtree.  Leaves
print their digit and leave through a *ladder* of per-node exits -- one hop
reaches 255 lines and an n=3 tree is longer than that, so a leaf climbs out
through its ancestors rather than jumping to the end in one go.

Every distance is derived from the assembled index map, never counted by
hand, and the widths are a fixed point: sizing one jump moves every label
after it.

**The express, which is what carries a hop past one reach.**  A hop longer
than 255 lines used to be respelled at every waypoint, ~25 lines each, and
the waypoints of different hops fought over the same dead lines -- the
routing was iterative and its cost exploded past n=7.  ``DownAccLines``
does not consume the accumulator, so a long hop needs to spell its stride
*once*: the jump's own slot loads the accumulator and launches, and every
waypoint after that is a bare one-line ``DownAccLines`` that flies the
same stride again, give or take a few ``@nd``/``@id`` adjusters where the
stride has to change.

Those waypoints -- *rungs* -- are parked in *meadows*: blocks of dead
lines behind an unconditional jump, emitted at safe points between gadgets
every :data:`_MEADOW_SPACING` lines and sized to the express chains
crossing the point.  Control walking into a meadow hops over it; control
landing inside is a rung in flight.  Meadows are placed after every width
has settled, and laying a rung replaces a one-line placeholder with a
one-line instruction, so routing never moves a label: every chain is
planned against final coordinates and cannot interfere with another,
which is what replaced the old router's patience knob, rung-spacing knob
and 2031s n=8 price.

Demand is measured, not derived, so placement can still come up short.  A
chain the meadows cannot carry is a *shortfall* naming the window that
held no rung slot; the repair adds one meadow inside each distinct
window and reroutes from clean placeholders, at most :data:`_REPAIRS`
additions -- a budget with a certificate per round, not a search -- and a
table still short after it is refused with the window, never mis-routed.
"""

from esolangs.tools.boolean.helpers import _ASCII_ZERO, _validate_truth_table

#: Lines between the two landing sites of the branch gadget, fixed by the
#: ``@id`` spread: bit 1 lands at ``p+4`` and bit 0 at ``p+13``.
_WINDOW = 9

#: How far one ``DownAccLines`` reaches: the accumulator holds a byte.
_REACH = 255


def _set_acc(target: int) -> list[str]:
    """Lines loading ``target`` (0-255) whatever the accumulator held.

    Counting up costs ``target % 10`` single steps; overshooting to the
    next ten and counting back with ``@nt`` costs ``10 - target % 10``.
    The shorter of the two spells 8 in four lines instead of nine, which is
    what lets the nine-line window reach past a distance of 7.
    """
    up = ["@id"] * (target // 10) + ["@nd"] * (target % 10)
    over = -(-target // 10)
    down = ["@id"] * over + ["@nt"] * (over * 10 - target)
    return ["NnNn", *min(up, down, key=len)]


def _hop_width(distance: int) -> int:
    """Lines an unconditional hop of ``distance`` needs."""
    return len(_set_acc(distance)) + 1


#: Sizing passes ``_resolve`` allows before giving up.  It is a cap, not a
#: convergence argument: what it refuses is a layout whose widths are still
#: moving, and the express keeps every width local, so the settles seen
#: since it shipped are two-digit.
_PASSES = 4096

#: Longest distance the nine-line window can spell.  Not ``_REACH``: the
#: slot is fixed, so what fits is what ``_set_acc`` spells in eight lines.
#: Not monotonic in the distance either -- 70 costs nine lines where 69
#: costs ten -- so this is a scan rather than an inverted formula.
_WINDOW_REACH = max(d for d in range(_REACH + 1) if _hop_width(d) <= _WINDOW)

#: The widest slot any single hop can need, scanned rather than assumed:
#: an express jump's slot is fixed at this width, so it can spell whatever
#: first stride the routing later picks.
_EXPRESS = max(_hop_width(d) for d in range(_REACH + 1))

# The bit-0 jump sits one window behind its relay label, so when it is
# promoted to an express slot the window must spell _EXPRESS itself.
if _hop_width(_EXPRESS) > _WINDOW:
    raise AssertionError("express slot outgrew the window")


class _Jump:
    """A hop to ``label``, holding ``width`` lines until it is resolved.

    ``fixed`` marks a slot whose size is load-bearing geometry -- the
    nine-line window -- so it is checked for overflow rather than grown.

    ``express`` marks a jump promoted to a fixed :data:`_EXPRESS`-wide
    slot because its span outgrew one reach; the router later points it at
    ``to_line`` -- its first rung, or the target itself where the span
    shrank back under one reach by the time widths settled.
    """

    __slots__ = ("express", "fixed", "label", "to_line", "width")

    def __init__(
        self,
        label: str,
        width: int,
        *,
        fixed: bool = False,
    ) -> None:
        self.label = label
        self.width = width
        self.fixed = fixed
        self.express = False
        self.to_line: int | None = None


class _Label:
    """A named position, occupying no line."""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name


class _Safe:
    """A zero-width point between gadgets where a meadow may be laid.

    Only marked positions are eligible: splicing lines into the middle of
    the branch gadget would break its fixed nine-line offset, and a meadow
    starts with an accumulator-clobbering jump, so the point also has to be
    one where the accumulator is dead -- which every gadget boundary is,
    since every continuation begins with a read or a load.
    """

    __slots__ = ()


class _Rung:
    """One reserved dead line in a meadow, ``x`` until a chain claims it."""

    __slots__ = ("op",)

    def __init__(self) -> None:
        self.op = "x"


type _Item = str | _Jump | _Label | _Safe | _Rung


def _emit(table: str, n: int) -> list[_Item]:
    """Lay the tree out flat, leaving every jump unresolved."""
    counter = [0]
    out: list[_Item] = []

    def block(lo: int, hi: int, depth: int, exit_label: str) -> None:
        out.append(_Safe())
        window = table[lo:hi]
        if len(set(window)) == 1:
            # A constant subtree needs no more branching, but it still has
            # to *read* the inputs below it: the reads are the interface,
            # and a program that leaves them on the stream desynchronises
            # whatever runs next.  ``u`` alone consumes one and is dropped.
            out.extend(["u"] * (n - depth))
            out.extend(_set_acc(_ASCII_ZERO + int(window[0])))
            out.append("div")
            # Out through this node's exit rather than straight to the end:
            # one hop reaches 255 lines and the tree is longer than that.
            out.append(_Jump(exit_label, 2))
            return
        counter[0] += 1
        tag = counter[0]
        right, left, mine, relay = (f"{p}{tag}" for p in "RLXY")
        half = (hi - lo) // 2
        out.extend(["u", *["@dd"] * 4, *["@nt"] * 8])
        out.extend(["DownAccLines", "@id", "DownAccLines"])
        out.append("x")  # dead: bit 1 lands two on, bit 0 eleven on
        # Both landing sites hold jumps, so neither subtree has to fit in
        # the window: the window clears only the bit-0 jump to reach the
        # relay, and the relay -- free to be any width -- enters `right`.
        out.append(_Jump(relay, _WINDOW, fixed=True))
        # The relay label must stay exactly here: bit 0 lands on this jump
        # by the gadget's fixed nine-line offset.  Nothing is ever spliced
        # between gadget lines -- meadows go only where ``_Safe`` says.
        out.append(_Jump(left, 2))  # the bit-0 landing site
        out.append(_Label(relay))
        out.append(_Jump(right, 2))
        out.append(_Label(right))
        block(lo + half, hi, depth + 1, mine)
        out.append(_Label(left))
        block(lo, lo + half, depth + 1, mine)
        out.append(_Label(mine))
        out.append(_Jump(exit_label, 2))

    block(0, len(table), 0, "END")
    return out


def _index(items: list[_Item]) -> tuple[list[int], dict[str, int]]:
    """Return each item's starting line and every label's line."""
    starts: list[int] = []
    labels: dict[str, int] = {}
    line = 0
    for item in items:
        starts.append(line)
        if isinstance(item, _Label):
            labels[item.name] = line
        elif isinstance(item, _Jump):
            line += item.width
        elif not isinstance(item, _Safe):
            line += 1
    labels["END"] = line
    return starts, labels


def _resolve(items: list[_Item]) -> None:
    """Size every growable jump, iterating until no width changes.

    A jump's own width shifts every label after it, so this is a fixed
    point rather than one pass.  A width can shrink as well as grow, so
    the bound is measured rather than argued -- and with every long span
    parked at the fixed express width, what is left to move is local.
    """
    moving = 0
    for _ in range(_PASSES):
        starts, labels = _index(items)
        moving = 0
        for item, start in zip(items, starts, strict=True):
            if not isinstance(item, _Jump) or item.fixed or item.express:
                # A fixed slot cannot grow: the window is checked at
                # emission, and an express slot spells any first stride.
                continue
            distance = labels[item.label] - (start + item.width)
            need = _hop_width(max(distance, 0))
            if need != item.width:
                item.width = need
                moving += 1
        if not moving:
            return
    raise ValueError(
        f"jump widths did not converge in {_PASSES} passes: {moving} jumps still moving"
    )


def _settle(items: list[_Item]) -> None:
    """Size widths and promote over-reach jumps until neither moves.

    Promotion is monotone -- an express jump never demotes, and promoting
    one only pushes labels apart -- so the alternation converges; the
    bound is the jump count, since each round must promote at least one.
    """
    while True:
        _resolve(items)
        starts, labels = _index(items)
        promoted = 0
        for item, start in zip(items, starts, strict=True):
            if not isinstance(item, _Jump) or item.fixed or item.express:
                continue
            if labels[item.label] - (start + item.width) > _REACH:
                item.express = True
                item.width = _EXPRESS
                promoted += 1
        if not promoted:
            return


#: Lines between meadows, measured on settled coordinates at placement.
#: The binding constraint is a hop between *cursors*: a chain may leave a
#: meadow near its start and land in the next near its end, so the pitch
#: between meadow starts plus a whole meadow of drift must stay inside one
#: reach -- and the pitch seen at run time is this figure stretched by the
#: guards and promotions that settle afterwards, so it sits well under
#: that bound.  The router's own reach check refuses a layout that
#: stretched too far anyway.
_MEADOW_SPACING = 80

#: Dead lines per meadow: the floor, the ceiling, and the lines added per
#: express chain crossing the placement point.  Demand is not uniform --
#: a meadow under a busy subtree carries a rung and a few adjusters for
#: every chain over it, plus the terminals of the label cluster behind it
#: -- so capacity follows the measured crossings instead of one number.
#: The ceiling is a reach constraint, not thrift: a hop may leave one
#: meadow's start and land at the next one's end, so two meadows and the
#: pitch between them must stay inside one reach.
_MEADOW_LEAST = 24
_MEADOW_MOST = 56
_MEADOW_PER_CHAIN = 6

#: Meadows the repair may add at shortfalls before a table is refused.
#: A budget on additions, not a convergence argument: four n=10 dense
#: seeds spend 95-126 across a handful of rounds, so this is the worst
#: measured with room over, and the programs past it are ones this
#: generator should refuse rather than chase.
_REPAIRS = 256


def _spans(items: list[_Item]) -> list[tuple[int, int]]:
    """Every express jump's (launch, target), on current coordinates."""
    starts, labels = _index(items)
    return [
        (start + item.width, labels[item.label])
        for item, start in zip(items, starts, strict=True)
        if isinstance(item, _Jump) and item.express
    ]


def _meadow(size: int, tag: int) -> tuple[list[_Rung], list[_Item]]:
    """One meadow: its rungs, and the guard-jump block that carries them."""
    rungs = [_Rung() for _ in range(size)]
    skip = f"M{tag}"
    return rungs, [_Jump(skip, 2), *rungs, _Label(skip)]


def _place(items: list[_Item]) -> list[list[_Rung]]:
    """Lay a meadow at every safe point one spacing past the last.

    Runs on settled coordinates, so the spacing seen here is real; the
    guards and promotions that follow stretch it, which is why the pitch
    sits well under the reach.  Each meadow is sized to the express
    chains crossing its point.  The sentinels are kept: a routing
    shortfall later adds meadows at them (:func:`_add`).
    """
    starts, _labels = _index(items)
    spans = _spans(items)
    out: list[_Item] = []
    meadows: list[list[_Rung]] = []
    last = 0
    for item, start in zip(items, starts, strict=True):
        if isinstance(item, _Safe) and start - last >= _MEADOW_SPACING:
            crossing = sum(low < start < high for low, high in spans)
            size = min(_MEADOW_MOST, _MEADOW_LEAST + _MEADOW_PER_CHAIN * crossing)
            rungs, block = _meadow(size, len(meadows))
            out.extend(block)
            meadows.append(rungs)
            last = start
        out.append(item)
    items[:] = out
    return meadows


def _add(items: list[_Item], meadows: list[list[_Rung]], low: int, high: int) -> None:
    """Insert one more meadow inside the shortfall window ``(low, high)``.

    The repair for a routing shortfall: the refusal names the window that
    held no usable rung slot, and the meadow goes at the last safe point
    inside it -- nearest whatever the stranded chain was reaching for.
    Falls back to the nearest safe point when the window holds none.
    """
    starts, _labels = _index(items)
    at = None
    fallback = None
    for position, (item, start) in enumerate(zip(items, starts, strict=True)):
        if not isinstance(item, _Safe):
            continue
        if start >= high:
            break
        fallback = position
        if start > low:
            at = position
    if at is None:
        at = fallback
    if at is None:
        raise AssertionError("a tree always emits safe points")
    rungs, block = _meadow(_MEADOW_MOST, len(meadows))
    items[at:at] = block
    meadows.append(rungs)


def _adjust(current: int, wanted: int) -> list[str]:
    """Return the shortest lines turning ``current`` into ``wanted``.

    Either nudged with ``@id``/``@dd`` tens and ``@nd``/``@nt`` units --
    the usual case, since consecutive strides differ by a meadow pitch or
    two -- or respelled from zero where that is shorter.
    """
    delta = wanted - current
    best: list[str] | None = None
    for tens in range(delta // 10 - 1, delta // 10 + 2):
        units = delta - 10 * tens
        ops = ["@id" if tens > 0 else "@dd"] * abs(tens)
        ops += ["@nd" if units > 0 else "@nt"] * abs(units)
        if best is None or len(ops) < len(best):
            best = ops
    if best is None:
        raise AssertionError("the tens scan always yields a candidate")
    return min(best, _set_acc(wanted), key=len)


class _Bank:
    """One meadow's allocation state: its rungs, their lines, a cursor."""

    __slots__ = ("cursor", "lines", "rungs")

    def __init__(self, rungs: list[_Rung], lines: list[int]) -> None:
        self.rungs = rungs
        self.lines = lines
        self.cursor = 0

    @property
    def line(self) -> int | None:
        """Where the next rung would land, or ``None`` when full."""
        if self.cursor >= len(self.rungs):
            return None
        return self.lines[self.cursor]

    @property
    def free(self) -> int:
        return len(self.rungs) - self.cursor

    def lay(self, ops: list[str], length: int) -> None:
        """Claim ``length`` lines: pads, then ``ops``, then the hop."""
        body = ["x"] * (length - len(ops) - 1) + ops + ["DownAccLines"]
        for rung, op in zip(
            self.rungs[self.cursor : self.cursor + length], body, strict=True
        ):
            rung.op = op
        self.cursor += length


def _lay(bank: _Bank, acc: int | None, landing: int, wanted: int) -> int | None:
    """Lay one rung in ``bank`` carrying ``acc`` from ``landing`` to ``wanted``.

    ``acc`` is ``None`` for a terminal rung, whose incoming accumulator is
    only decided when the approach to it is routed later -- so its body
    must respell from zero rather than adjust.

    The rung's length and its stride are coupled: a longer body launches
    from further down, which shrinks the stride, which changes the body.
    Scanned rather than solved -- lengths are small -- taking the first
    length whose body fits, padded in front so the hop stays at the end.
    Returns the stride flown, or ``None`` where nothing fits.
    """
    for length in range(1, min(bank.free, _EXPRESS) + 1):
        stride = wanted - landing - length
        if not 0 <= stride <= _REACH:
            continue
        if acc is None:
            ops = _set_acc(stride)
        else:
            ops = [] if stride == acc else _adjust(acc, stride)
        if len(ops) + 1 <= length:
            bank.lay(ops, length)
            return stride
    return None


def _fits(free: int, landing: int, target: int, acc: int | None = None) -> bool:
    """Whether a terminal rung landing at ``landing`` can finish in ``free``.

    Mirrors :func:`_lay` with no allocation.  With ``acc`` unknown the
    body is priced as a respell -- the worst a terminal can need, since
    the real lay adjusts from the accumulator the approach delivers when
    that is shorter -- so a bank that passes is guaranteed to take the
    rung later.  A terminal the entry hop reaches directly knows its
    accumulator already, and pricing the true adjusters lets it fit in
    room a respell could not.
    """
    for length in range(1, min(free, _EXPRESS) + 1):
        stride = target - landing - length
        if not 0 <= stride <= _REACH:
            continue
        if acc is None:
            need = _hop_width(stride)
        else:
            ops = [] if stride == acc else _adjust(acc, stride)
            need = len(ops) + 1
        if need <= length:
            return True
    return False


class _StuckError(ValueError):
    """One routing shortfall, naming the window that held no rung slot.

    A :class:`ValueError` so an unrepaired shortfall is the generator's
    ordinary refusal; the window is where :func:`_add` repairs.  For a
    stranded approach that is the reach ahead of its landing; for a chain
    that found no terminal it is the stretch before its target.
    """

    def __init__(self, low: int, high: int, label: str) -> None:
        super().__init__(
            f"no rung slot in lines {low}-{high} for the jump to {label} "
            f"-- every meadow there is full or out of reach"
        )
        self.low = low
        self.high = high


def _route(items: list[_Item], meadows: list[list[_Rung]]) -> list[_StuckError]:
    """Point every express jump at its chain, laying rungs in meadows.

    Coordinates are final -- laying a rung rewrites a placeholder line in
    place -- so chains are planned once, greedily, each hop taking the
    furthest meadow in reach.  A chain that finds no meadow it can use is
    a shortfall by name, never a mis-routed program; every shortfall of
    the pass is returned together, so one repair round serves them all.
    """
    starts, labels = _index(items)
    position = {id(item): start for item, start in zip(items, starts, strict=True)}
    banks = [_Bank(rungs, [position[id(rung)] for rung in rungs]) for rungs in meadows]

    def refuse(landing: int, until: int, label: str) -> _StuckError:
        return _StuckError(landing, until, label)

    def onward(landing: int, until: int) -> list[_Bank]:
        """Banks a hop from ``landing`` could land in, furthest first.

        Room for a typical adjuster rung is demanded up front, so a chain
        never hops into a bank it cannot leave: consecutive strides differ
        by a meadow pitch or two, well inside what thirteen adjusters fix.
        """
        ahead = [
            bank
            for bank in banks
            if bank.line is not None
            and landing < bank.line <= until
            and bank.line - landing <= _REACH
            and bank.free >= 14
        ]
        ahead.sort(key=lambda bank: -(bank.line or 0))
        return ahead

    chains = [
        (item, start + item.width, labels[item.label])
        for item, start in zip(items, starts, strict=True)
        if isinstance(item, _Jump) and item.express
    ]

    def route(item: _Jump, launch: int, target: int) -> None:
        if 0 <= target - launch <= _REACH:
            item.to_line = target  # the span settled back under one reach
            return
        # The terminal bank -- the chain's last stop -- is chosen first,
        # nearest the target with room for a worst-case finish, so the
        # chain never discovers at its last stop that the room for the
        # finish was already spent.  Its rung is *laid* last, though: the
        # accumulator it inherits is only decided by the approach, and a
        # known accumulator turns the finish from a respell into a few
        # adjusters.  Excluding it from the approach keeps its room whole.
        terminal = next(
            (
                bank
                for bank in sorted(banks, key=lambda b: -(b.line or 0))
                if bank.line is not None
                and launch < bank.line < target
                and target - bank.line <= _REACH
                and _fits(
                    bank.free,
                    bank.line,
                    target,
                    bank.line - launch if bank.line - launch <= _REACH else None,
                )
            ),
            None,
        )
        if terminal is None or terminal.line is None:
            # The shortfall is in the terminal window before the target,
            # wherever the launch was.
            raise refuse(max(launch, target - _REACH), target, item.label)
        stop = terminal.line
        if stop - launch <= _REACH:
            item.to_line = stop  # the entry hop reaches the terminal alone
            acc = stop - launch
        else:
            first = [b for b in onward(launch, stop) if b is not terminal]
            if not first:
                raise refuse(launch, min(stop, launch + _REACH), item.label)
            bank = first[0]
            landing = bank.line or 0
            item.to_line = landing
            acc = landing - launch
            while True:
                # ``landing`` is the cursor line of ``bank``, where this
                # chain's next rung must be laid; ride until one of those
                # rungs can land exactly on the terminal.
                if stop - landing <= _REACH:
                    hop = _lay(bank, acc, landing, stop)
                    if hop is not None:
                        acc = hop
                        break
                for goal in onward(landing, stop):
                    goal_line = goal.line
                    if goal is terminal or goal_line is None:
                        continue
                    hop = _lay(bank, acc, landing, goal_line)
                    if hop is not None:
                        acc, landing, bank = hop, goal_line, goal
                        break
                else:
                    raise refuse(landing, min(stop, landing + _REACH), item.label)
        if _lay(terminal, acc, stop, target) is None:
            raise refuse(stop, target, item.label)

    stuck: list[_StuckError] = []
    for item, launch, target in chains:
        try:
            route(item, launch, target)
        except _StuckError as shortfall:
            # Collect rather than stop: every stranded chain names its
            # window in one pass, so one repair round serves them all.
            # Rungs a chain laid before stranding stay claimed, which is
            # fine -- a repaired attempt starts from clean placeholders.
            stuck.append(shortfall)
    return stuck


def _check(label: str, distance: int, width: int) -> None:
    """Refuse a jump the gadget cannot spell, naming which and by how much."""
    if not 0 <= distance <= _REACH:
        raise ValueError(f"jump to {label} spans {distance} lines (max {_REACH})")
    if _hop_width(distance) > width:
        raise ValueError(
            f"jump to {label} needs {_hop_width(distance)} lines, has {width}"
        )


def interprogck8(truth_table: str) -> str:
    """Return a program printing ``truth_table``'s result for its inputs.

    Reads ``n`` digits, one per line, and prints ``0`` or ``1``.
    """
    n = _validate_truth_table(truth_table)
    items = _emit(truth_table, n)
    # Widths first, so meadows are placed on real coordinates; then widths
    # again, since the meadows' guards and the jumps that now span a meadow
    # move labels.  Both settles are fixed points, not searches, and the
    # routing after them is a single pass against frozen coordinates.
    _settle(items)
    meadows = _place(items)
    _settle(items)
    # Routing is a single pass against frozen coordinates, but demand is
    # measured, not derived: every stranded chain names the window whose
    # reach held no usable rung slot, a meadow is added in each distinct
    # window, and the whole route is retried from clean placeholders.
    # Each round adds capacity at certificates, so the loop is a bounded
    # repair, not a search; a table still short after the budget is
    # refused with one of its remaining shortfalls.
    added = 0
    while True:
        stuck = _route(items, meadows)
        if not stuck:
            break
        if added > _REPAIRS:
            raise stuck[0]
        for rungs in meadows:
            for rung in rungs:
                rung.op = "x"
        for item in items:
            if isinstance(item, _Jump):
                item.to_line = None
        # Highest window first, so the insertions this round leave the
        # coordinates of the windows still waiting untouched; windows
        # overlapping one already served this round share its meadow.
        served: list[tuple[int, int]] = []
        for shortfall in sorted(stuck, key=lambda s: -s.low):
            if any(shortfall.low < hi and lo < shortfall.high for lo, hi in served):
                continue
            _add(items, meadows, shortfall.low, shortfall.high)
            served.append((shortfall.low, shortfall.high))
            added += 1
        _settle(items)
    starts, labels = _index(items)
    out: list[str] = []
    for item, start in zip(items, starts, strict=True):
        if isinstance(item, (_Label, _Safe)):
            continue
        if isinstance(item, _Rung):
            out.append(item.op)
            continue
        if isinstance(item, _Jump):
            goal = item.to_line if item.to_line is not None else labels[item.label]
            distance = goal - (start + item.width)
            _check(item.label, distance, item.width)
            patch = [*_set_acc(distance), "DownAccLines"]
            # Pad ahead of the hop so its jump stays at the slot's end.
            out.extend(["x"] * (item.width - len(patch)) + patch)
        else:
            out.append(item)
    return "\n".join(out)
