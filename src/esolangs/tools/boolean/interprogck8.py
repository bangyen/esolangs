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
any line up to 255 ahead, and further by relaying (below).

**Layout.**  Both landing sites hold jumps rather than code, so neither arm
has to be spelled inside the nine-line window: the window hops to a relay
just past the bit-0 jump, and the relay enters the bit-1 subtree.  Leaves
print their digit and leave through a *ladder* of per-node exits -- one hop
reaches 255 lines and an n=3 tree is longer than that, so a leaf climbs out
through its ancestors rather than jumping to the end in one go.

Every distance is derived from the assembled index map, never counted by
hand, and the widths are a fixed point: sizing one jump moves every label
after it.

**Rungs, which is what lifted the arity cap.**  One hop reaches 255 lines
and the tree passes that at n=4: parity at n=5 is 2688 lines with bit-0
crossings over 1000.  A hop that long is broken over *rungs* -- jumps
onward to the same place, parked in the dead line just past an
unconditional jump, where control never falls in.  Each rung opens another
dead line behind it, so the chain reaches as far as it must, and the
nine-line window heals itself: its distance is the bit-0 jump's own width,
which collapses once that jump becomes a short hop to the first rung.

Two lines in the gadget are *not* dead space, though they follow a jump.
The relay label has to sit immediately after the bit-0 jump, because bit 0
lands on that jump by the gadget's fixed nine-line offset -- so that jump
is sealed and no rung is parked behind it.  Parking one there routes the
tree through arbitrary code, which printed the wrong bit on 40 rows before
the seal existed.
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


#: Sizing passes ``_resolve`` allows before giving up.  The routing loop
#: has its own guard (:data:`_PATIENCE`), which measures progress rather
#: than counting.  820 passes is the worst measured (parity at n=7), so
#: this bounds a sizing that has stopped settling rather than pacing one
#: that is still working -- but it is a cap, not a convergence argument,
#: and the number it can afford grows with the table.
_PASSES = 4096

#: Longest distance the nine-line window can spell.  Not ``_REACH``: the
#: slot is fixed, so what fits is what ``_set_acc`` spells in eight lines.
#: Not monotonic in the distance either -- 70 costs nine lines where 69
#: costs ten -- so this is a scan rather than an inverted formula.
_WINDOW_REACH = max(d for d in range(_REACH + 1) if _hop_width(d) <= _WINDOW)


class _Jump:
    """A hop to ``label``, holding ``width`` lines until it is resolved.

    ``fixed`` marks a slot whose size is load-bearing geometry -- the
    nine-line window -- so it is checked for overflow rather than grown.

    ``sealed`` marks a jump whose *following* line is part of the gadget's
    geometry rather than dead space, so no rung may be parked after it.
    """

    __slots__ = ("fixed", "label", "sealed", "width")

    def __init__(
        self,
        label: str,
        width: int,
        *,
        fixed: bool = False,
        sealed: bool = False,
    ) -> None:
        self.label = label
        self.width = width
        self.fixed = fixed
        self.sealed = sealed


class _Label:
    """A named position, occupying no line."""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name


type _Item = str | _Jump | _Label


def _emit(table: str, n: int) -> list[_Item]:
    """Lay the tree out flat, leaving every jump unresolved."""
    counter = [0]
    out: list[_Item] = []

    def block(lo: int, hi: int, depth: int, exit_label: str) -> None:
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
        # Sealed: the relay label must stay exactly here.  Bit 0 lands on
        # this jump by the gadget's fixed nine-line offset, so a rung
        # parked after it would move the relay and the landing site both.
        out.append(_Jump(left, 2, sealed=True))  # the bit-0 landing site
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
        else:
            line += 1
    labels["END"] = line
    return starts, labels


#: Rounds the router may go without beating its best over-reach count
#: before it gives up.  Generous because the count rises before it falls:
#: n=8 dense peaks in round 3 and takes until round 10 to come back under
#: its round-1 value, so a tight patience would refuse a table that routes.
_PATIENCE = 32

#: How far apart rungs of one chain are parked.  Under :data:`_REACH`, and
#: the slack is what makes a chain survive being laid: sizing the rungs and
#: laying other chains both push lines apart afterwards, so a chain spaced
#: at the reach itself would be over it by the time it was sized.  Slots
#: recur every 100 lines at worst, so a gap this wide always has one.
_SPACING = 200


def _relay(items: list[_Item]) -> bool:
    """Break every out-of-reach jump into a chain of rungs, in one go.

    One ``DownAccLines`` reaches :data:`_REACH` lines and the tree is far
    longer than that above n=3 -- 2109 lines for parity at n=5, carrying
    hops of 1036.  A hop that cannot be spelled in one go is spelled in
    several, which needs somewhere to land in between.

    A rung is a real jump onward, not a marker: a hop that lands on a bare
    label runs whatever follows it in the stream, which is how a rerouted
    tree once printed the wrong bit on 40 rows.

    Where one can be parked is the whole constraint.  The slot has to be a
    line control never falls into, or the rung would run as part of what
    precedes it -- and the line just past an unconditional jump is exactly
    that, since the jump always leaves.

    **The whole chain is laid at once**, which is the difference between
    this terminating and not.  Extending a chain by one rung per round
    looked equivalent and was not: every round each of ~22 open chains
    inserted a rung, and the insertions landing inside the other chains'
    spans pushed their targets further away than the rung had gained.  At
    n=7 the count of over-reach jumps rose from 22 to 198 while the program
    grew to 47k lines -- the chase diverged rather than converged.
    """
    starts, labels = _index(items)
    # Dead slots, by the index of the item that must follow them.
    slots: dict[int, int] = {}
    for position, (item, start) in enumerate(zip(items, starts, strict=True)):
        if isinstance(item, _Jump) and not item.fixed and not item.sealed:
            slots[position + 1] = start + item.width
    by_line = sorted((line, position) for position, line in slots.items())
    laid: dict[int, list[_Item]] = {}
    tag = sum(isinstance(i, _Jump) for i in items)
    for item, start in zip(items, starts, strict=True):
        if not isinstance(item, _Jump) or item.fixed:
            # The window is not rerouted: its distance is the bit-0 jump's
            # own width, so it shrinks back on its own once that jump is
            # broken over a rung.
            continue
        here = start + item.width
        target = labels[item.label]
        if 0 <= target - here <= _REACH:
            continue
        # Step towards the target, taking the furthest slot within one
        # spacing each time, until the last rung can finish in one hop.
        chain: list[int] = []
        line = here
        while target - line > _REACH:
            reachable = [
                (slot_line, position)
                for slot_line, position in by_line
                if line < slot_line <= min(line + _SPACING, target)
            ]
            if not reachable:
                break
            line, position = max(reachable)
            chain.append(position)
        if not chain:
            continue
        # Link each rung to the next and the last to the real destination,
        # then send the original jump to the first.
        names = [f"P{tag + i}" for i in range(1, len(chain) + 1)]
        tag += len(chain)
        onward = [*names[1:], item.label]
        for position, name, goes_to in zip(chain, names, onward, strict=True):
            laid.setdefault(position, []).extend([_Label(name), _Jump(goes_to, 2)])
        item.label = names[0]
    if not laid:
        return False
    out: list[_Item] = []
    for position, item in enumerate(items):
        out.extend(laid.get(position, ()))
        out.append(item)
    out.extend(laid.get(len(items), ()))
    items[:] = out
    return True


def _over_reach(items: list[_Item]) -> int:
    """How many jumps still span further than one hop can carry."""
    starts, labels = _index(items)
    return sum(
        not 0 <= labels[item.label] - (start + item.width) <= _REACH
        for item, start in zip(items, starts, strict=True)
        if isinstance(item, _Jump)
    )


def _resolve(items: list[_Item]) -> None:
    """Size every growable jump, iterating until no width changes.

    A jump's own width shifts every label after it, so this is a fixed
    point rather than one pass.  A width can shrink as well as grow -- a
    rerouted jump spells a shorter distance -- so the bound is measured
    rather than argued: the worst settle is 820 passes (parity at n=7), and
    the count of moving jumps wobbles on its way down rather than falling
    monotonically, so a pass that changes more than the last one is not a
    sign of trouble.
    """
    moving = 0
    for _ in range(_PASSES):
        starts, labels = _index(items)
        moving = 0
        for item, start in zip(items, starts, strict=True):
            if not isinstance(item, _Jump):
                continue
            distance = labels[item.label] - (start + item.width)
            if item.fixed:
                # A fixed slot cannot grow, so an overflow is not sized
                # away here -- ``_retarget`` reroutes it and the emission
                # pass checks what survives.  Checking here instead would
                # refuse a jump that the next reroute was about to fix.
                continue
            need = _hop_width(max(distance, 0))
            if need != item.width:
                item.width = need
                moving += 1
        if not moving:
            return
    # Not reached by anything built so far -- parity at n=7 is the worst
    # measured, at 820 of these passes.  What it would refuse is a program
    # whose widths were still moving, not one that cannot be laid out: a
    # reroute can shrink a width as well as grow one, so the settle is
    # measured rather than argued and wants a backstop.
    raise ValueError(
        f"jump widths did not converge in {_PASSES} passes: {moving} jumps still moving"
    )


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
    # Sizing and rerouting feed each other: a rerouted jump changes width,
    # which moves every label after it, which can pull another jump out of
    # reach.  Alternate until neither pass has anything left to do.
    #
    # The guard is progress, not a pass count.  A cap alone would report a
    # table as unbuildable when the routing was merely slow, and -- worse --
    # would have hidden the one-rung-per-round relay that used to *lose*
    # ground here, taking the over-reach count from 22 up to 198 while the
    # program tripled.  Each round must leave strictly fewer jumps out of
    # reach; when one does not, that count is the certificate of the stall.
    best = len(items)
    stuck = 0
    while True:
        _resolve(items)
        if not _relay(items):
            break
        remaining = _over_reach(items)
        if remaining < best:
            best, stuck = remaining, 0
            continue
        # A round that does not improve is not yet a stall.  Laying a chain
        # pushes later labels apart, so a table can get worse before it
        # gets better -- n=8 dense peaks at 256 over-reach jumps in round 3
        # and is back under 110 by round 10.  Only a run of rounds that
        # never beats the best seen is evidence the routing has stopped
        # gaining, and then the count is the certificate.
        stuck += 1
        if stuck > _PATIENCE:
            raise ValueError(
                f"jump routing stalled: {remaining} jumps past the "
                f"{_REACH}-line reach, and {_PATIENCE} rounds without "
                f"improving on {best}"
            )
    starts, labels = _index(items)
    out: list[str] = []
    for item, start in zip(items, starts, strict=True):
        if isinstance(item, _Label):
            continue
        if isinstance(item, _Jump):
            distance = labels[item.label] - (start + item.width)
            _check(item.label, distance, item.width)
            patch = [*_set_acc(distance), "DownAccLines"]
            # Pad ahead of the hop so its jump stays at the slot's end.
            out.extend(["x"] * (item.width - len(patch)) + patch)
        else:
            out.append(item)
    return "\n".join(out)
