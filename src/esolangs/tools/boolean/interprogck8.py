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
any line up to 255 ahead.

**Layout.**  Both landing sites hold jumps rather than code, so neither arm
has to be spelled inside the nine-line window: the window hops to a relay
just past the bit-0 jump, and the relay enters the bit-1 subtree.  Leaves
print their digit and leave through a *ladder* of per-node exits -- one hop
reaches 255 lines and an n=3 tree is longer than that, so a leaf climbs out
through its ancestors rather than jumping to the end in one go.

Every distance is derived from the assembled index map, never counted by
hand, and the widths are a fixed point: sizing one jump moves every label
after it.

**The arity cap is this construction's, not the language's.**  At n=4 the
bit-0 jump has to clear a 456-line subtree against a 255 ceiling, and the
nine-line window spells at most 70.  A rung parked inside the crossed
region would lift both, so the cap is a bound on what is built here and
tested, not a wall -- ``ValueError`` above 3 keeps the claim and the code
in step.
"""

from esolangs.tools.boolean.helpers import _ASCII_ZERO, _validate_truth_table

#: Lines between the two landing sites of the branch gadget, fixed by the
#: ``@id`` spread: bit 1 lands at ``p+4`` and bit 0 at ``p+13``.
_WINDOW = 9

#: Highest arity this construction places.  See the module docstring: at 4
#: the bit-0 crossing needs 456 lines and one ``DownAccLines`` reaches 255.
MAX_INPUTS = 3


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


class _Jump:
    """A hop to ``label``, holding ``width`` lines until it is resolved.

    ``fixed`` marks a slot whose size is load-bearing geometry -- the
    nine-line window -- so it is checked for overflow rather than grown.
    """

    __slots__ = ("fixed", "label", "width")

    def __init__(self, label: str, width: int, *, fixed: bool = False) -> None:
        self.label = label
        self.width = width
        self.fixed = fixed


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
        else:
            line += 1
    labels["END"] = line
    return starts, labels


def _resolve(items: list[_Item]) -> None:
    """Size every growable jump, iterating until no width changes.

    A jump's own width shifts every label after it, so this is a fixed
    point rather than one pass.  Widths only grow, and the program is
    finite, so it terminates.
    """
    for _ in range(64):
        starts, labels = _index(items)
        changed = False
        for item, start in zip(items, starts, strict=True):
            if not isinstance(item, _Jump):
                continue
            distance = labels[item.label] - (start + item.width)
            if item.fixed:
                # A fixed slot cannot grow, so an oversized patch would be
                # emitted silently and shift every later line -- which is
                # how bit 0 once landed on the window's own jump.
                _check(item.label, distance, item.width)
                continue
            need = _hop_width(max(distance, 0))
            if need != item.width:
                item.width = need
                changed = True
        if not changed:
            return
    raise ValueError("jump widths did not converge")  # pragma: no cover


def _check(label: str, distance: int, width: int) -> None:
    """Refuse a jump the gadget cannot spell, naming which and by how much."""
    if not 0 <= distance <= 255:
        raise ValueError(f"jump to {label} spans {distance} lines (max 255)")
    if _hop_width(distance) > width:
        raise ValueError(
            f"jump to {label} needs {_hop_width(distance)} lines, has {width}"
        )


def interprogck8(truth_table: str) -> str:
    """Return a program printing ``truth_table``'s result for its inputs.

    Reads ``n`` digits, one per line, and prints ``0`` or ``1``.  Raises
    :class:`ValueError` above :data:`MAX_INPUTS` -- see the module
    docstring for what the cap measures.
    """
    n = _validate_truth_table(truth_table)
    if n > MAX_INPUTS:
        raise ValueError(
            f"interprogck8 places at most {MAX_INPUTS} inputs, got {n}: "
            "the bit-0 crossing outgrows one DownAccLines above that"
        )
    items = _emit(truth_table, n)
    _resolve(items)
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
