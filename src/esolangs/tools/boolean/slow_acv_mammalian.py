"""Boolean-function generator for SLOW ACV MAMMALIAN.

The language reads a byte with ``ACCEPT``, which appends ``byte ^ acc`` to
array 0 *whatever the pointer holds*.  That is what makes a decision tree
possible: the older reading of the instruction set had the bit needing to be
routed to the pointer before it could be tested, which conflicts with using
``SPRINT`` to move the pointer anywhere else.  Nothing needs routing.  The
pointer stays on array 0 for the whole program and the tree lives in code
space, built out of the one conditional the language has:

``ACCEPT DIGEST LEAPFROG``
    ``ACCEPT`` appends the bit (entering with ``acc % 256 == 48``, the digit
    ``'0'``/``'1'`` normalizes to a clean ``0``/``1``), ``DIGEST`` folds the
    array sum into the accumulator, and ``LEAPFROG`` jumps exactly when the
    array's last element -- the bit just read -- is nonzero.  So a 0 falls
    through to the next token and a 1 jumps: one node of a binary decision
    tree, three tokens long.

Bits are never popped off the array, so on any path the machine state is a
constant known while generating, and every jump can be aimed by choosing
what the array holds.  Aiming is done by *measuring*, not by solving: every
arithmetic knob here ties the array head to the array sum (``SEED`` bumps
both), so the offsets that look independent cancel, and each state reaches
only a handful of token indices.  What makes that enough is that a subtree
ends in a halting leaf -- the tokens after it are unreachable, so the
generator emits the node, measures where the 1-branch actually lands, and
pads the dead gap out to meet it.  Stashed bytes move the landing point
about 220 tokens per chunk against roughly 40 tokens of added layout, so the
jump overtakes the layout within a few rounds.

The tree is uniform depth ``n``: constant tables are not folded, because the
reads are the interface and every table has to consume all ``n`` inputs.
"""

from esolangs.tools.boolean.helpers import _ASCII_ZERO, _validate_truth_table

__all__ = ["slow_acv_mammalian_boolean"]

# How large a byte a stash chunk aims to append.  The chunk pays about 40
# tokens of layout for it, so a big byte is what makes the jump's reach grow
# faster than the program it has to jump over.
_STASH_BYTE = 220

# ``j1`` cancels out of the landing point, so sweeping it past one period of
# the mod-256 correction enumerates every gadget a state admits.
_J1_PERIOD = 64

# Stash chunks tried before the generator gives up on a node.  Reach grows
# ~220 tokens a chunk against ~40 of layout, so a node that has not converged
# in this many rounds is not going to.
_MAX_CHUNKS = 64


def _apply(op: str, array: list[int], acc: int) -> tuple[list[int], int]:
    """Apply one token to array 0, mirroring the interpreter.

    Only the three ops the generator emits outside a node are modelled:
    ``SEED`` bumps array 0's head by one (the array's index plus one, and
    this array is index 0), ``DIGEST`` XORs the array sum into the
    accumulator, and ``EXCRETE`` appends ``acc % 256`` and clears it.
    """
    if op == "SEED":
        out = list(array)
        out[0] = (out[0] + 1) % 256
        return out, acc
    if op == "DIGEST":
        return list(array), acc ^ sum(array)
    if op == "EXCRETE":
        out = list(array)
        out.append(acc % 256)
        return out, 0
    if op == "CONSUME":
        # Pops the middle element, which is what lets a node *lower* its
        # landing band: without it the array sum only ever grows, so every
        # node's reachable indices track the layout one-for-one and a node
        # can never jump over a subtree bigger than the fixed slack.
        out = list(array)
        return out, out.pop((len(out) - 1) // 2)
    raise ValueError(f"unmodelled token: {op}")


def _run(tokens: list[str], array: list[int], acc: int) -> tuple[list[int], int]:
    """Fold ``tokens`` over the state."""
    for op in tokens:
        array, acc = _apply(op, array, acc)
    return array, acc


def _reach_acc(array: list[int], acc: int, want: int) -> list[str] | None:
    """Tokens landing the accumulator in ``want``'s residue class mod 256.

    Only ``acc % 256`` is ever spent: ``ACCEPT`` appends ``byte ^ acc`` and
    ``PRONOUNCE`` prints ``chr(acc % 256)``.  Asking for the residue rather
    than the value keeps the search bounded once the array sum runs into the
    thousands, where an exact match may need more than 255 ``SEED``s.

    Each family ends in ``DIGEST`` so the accumulator picks up the sum; the
    prefixes differ in how they move the sum first.  Stored bits survive all
    of them -- ``SEED`` only touches the head, ``EXCRETE`` only appends.
    """
    best: list[str] | None = None
    for prefix in ([], ["DIGEST"], ["EXCRETE"], ["DIGEST", "EXCRETE"]):
        cursor, value = _run(prefix, array, acc)
        for count in range(256):
            if (value ^ sum(cursor)) % 256 == want % 256:
                candidate = [*prefix, *["SEED"] * count, "DIGEST"]
                if best is None or len(candidate) < len(best):
                    best = candidate
                break
            cursor, value = _apply("SEED", cursor, value)
    return best


def _leaf(array: list[int], acc: int, bit: int) -> list[str]:
    """Print the table entry, then halt."""
    tokens = _reach_acc(array, acc, _ASCII_ZERO + bit)
    if tokens is None:  # pragma: no cover - a residue is always reachable
        raise ValueError("no accumulator normalizer for a leaf")
    # ``EXCRETE`` appends the printed byte (48 or 49, so nonzero: ``LEAPFROG``
    # fires) and clears the accumulator, which makes the jump target
    # ``0 - head - 1``.  That is negative, which the interpreter halts on.
    return [*tokens, "PRONOUNCE", "EXCRETE", "LEAPFROG"]


def _stash_chunk(array: list[int], acc: int) -> list[str]:
    """``SEED*j DIGEST EXCRETE``, appending as large a byte as it can find.

    The appended byte is what grows the array sum, and the sum is what puts
    a distant token index within the jump's reach.
    """
    cursor, value = list(array), acc
    for count in range(256):
        if (value ^ sum(cursor)) % 256 >= _STASH_BYTE:
            return [*["SEED"] * count, "DIGEST", "EXCRETE"]
        cursor, value = _apply("SEED", cursor, value)
    return ["DIGEST", "EXCRETE"]  # pragma: no cover - a byte is always found


def _shed_chunk(array: list[int]) -> list[str] | None:
    """One ``CONSUME``, dropping the array's middle element.

    The counterpart to :func:`_stash_chunk`.  Growing the sum raises where a
    node can jump to, and a 0-subtree inherits its parent's array, so without
    a way *down* every node's reach tracks the layout it has to clear and the
    tree stops converging past two levels.  Shedding lowers the band instead.

    The head and the last element are what ``LEAPFROG`` reads, and a middle
    pop touches neither; the bits already branched on are ballast, since
    their values are known to the generator on this path.
    """
    if len(array) < 3:  # keep the head plus one element to pop next time
        return None
    return ["CONSUME"]


def _read_gadget(array: list[int], acc: int, first: int) -> list[str] | None:
    """``EXCRETE SEED*j1 DIGEST SEED*j2 DIGEST``, leaving ``acc % 256 == 48``.

    A gadget ending in a single ``DIGEST`` always exits with the accumulator
    *equal* to the sum, and the node's ``acc ^ (sum + 1)`` then collapses to
    1 however large the sum grew.  Loading the accumulator before the last
    ``SEED`` run breaks that tie: the run leaves ``acc = S1 ^ S2`` against a
    sum of ``S2``, and ``j2`` is forced by ``ACCEPT``'s convention that the
    accumulator read a clean digit.

    A ``SEED`` run that carries the head past 255 drops the sum by 256
    partway through, so the head is wrapped to 0 first when the room left is
    too small.
    """
    for wrap in (False, True):
        prefix = ["SEED"] * ((256 - array[0]) % 256) if wrap else []
        cursor, value = _run(prefix, array, acc)
        excreted, _ = _apply("EXCRETE", cursor, value)
        start, head = sum(excreted), excreted[0]
        j1 = first - start
        if j1 < 0:
            continue
        j2 = (((start + j1) ^ _ASCII_ZERO) - (start + j1)) % 256
        if head + j1 + j2 > 255:
            continue
        tokens = [
            *prefix,
            "EXCRETE",
            *["SEED"] * j1,
            "DIGEST",
            *["SEED"] * j2,
            "DIGEST",
        ]
        if _run(tokens, array, acc)[1] % 256 == _ASCII_ZERO:
            return tokens
    return None


def _landing_points(array: list[int], acc: int) -> dict[int, list[str]]:
    """Every ``(landing token, gadget)`` this state can reach.

    ``j1`` cancels out of the landing point -- each ``SEED`` moves the head
    and the sum together -- so the reachable set is small and sweeping one
    period of the correction enumerates all of it.
    """
    excreted, _ = _apply("EXCRETE", array, acc)
    start = sum(excreted)
    found: dict[int, list[str]] = {}
    for j1 in range(_J1_PERIOD):
        gadget = _read_gadget(array, acc, start + j1)
        if gadget is None:
            continue
        cursor, value = _run(gadget, array, acc)
        taken = [*cursor, 1]
        found.setdefault((value ^ sum(taken)) - taken[0], gadget)
    return found


def _sum_prefixes(array: list[int], acc: int) -> list[list[str]]:
    """Array adjustments to try before a node's read gadget, nearest first.

    Each entry moves the array sum, which is what moves the band of token
    indices the node's jump can reach: ``CONSUME`` pops a stashed byte to
    lower it, a stash chunk appends one to raise it.  Trying the empty
    adjustment first keeps a node that already aligns from paying for one.
    """
    out: list[list[str]] = [[]]

    sheds: list[str] = []
    cursor, value = list(array), acc
    while True:
        chunk = _shed_chunk(cursor)
        if chunk is None or len(sheds) >= _MAX_CHUNKS:
            break
        sheds = [*sheds, *chunk]
        cursor, value = _run(chunk, cursor, value)
        out.append(list(sheds))

    grows: list[str] = []
    cursor, value = list(array), acc
    for _ in range(_MAX_CHUNKS):
        chunk = _stash_chunk(cursor, value)
        grows = [*grows, *chunk]
        cursor, value = _run(chunk, cursor, value)
        out.append(list(grows))
    return out


def _subtree(
    table: str, n: int, depth: int, row: str, array: list[int], acc: int, base: int
) -> list[str]:
    """Build the subtree rooted here, knowing it starts at token ``base``."""
    if depth == n:
        return _leaf(array, acc, int(table[int(row, 2) if row else 0]))

    # A node's reachable indices sit in a band around the array sum, so
    # aligning the jump is a matter of moving the sum: stash bytes to raise
    # the band, CONSUME them back to lower it.  Both directions are needed --
    # a 0-subtree inherits its parent's array, so if the sum could only grow
    # its landings would track the layout it has to clear and nothing past
    # two levels would converge.
    for prefix in _sum_prefixes(array, acc):
        cursor, value = _run(prefix, array, acc)
        best: tuple[int, list[str], list[str], int, list[int], int, int] | None = None
        for landing, gadget in sorted(_landing_points(cursor, value).items()):
            after, folded = _run(gadget, cursor, value)
            node = [*prefix, *gadget, "ACCEPT", "DIGEST", "LEAPFROG"]
            fell = [*after, 0]
            try:
                zero = _subtree(
                    table,
                    n,
                    depth + 1,
                    row + "0",
                    fell,
                    folded ^ sum(fell),
                    base + len(node),
                )
            except ValueError:
                continue
            one_base = base + len(node) + len(zero)
            if landing < one_base:
                continue
            taken = [*after, 1]
            cost = len(node) + len(zero) + (landing - one_base)
            if best is None or cost < best[0]:
                best = (
                    cost,
                    node,
                    zero,
                    landing - one_base,
                    taken,
                    folded ^ sum(taken),
                    landing,
                )
        if best is not None:
            _, node, zero, pad, taken, taken_acc, landing = best
            try:
                one = _subtree(
                    table, n, depth + 1, row + "1", taken, taken_acc, landing
                )
            except ValueError:
                continue
            # The pad lands after the 0-subtree's halting leaf, so it is never
            # executed; it only pushes the 1-subtree out to where the jump goes.
            return [*node, *zero, *["SEED"] * pad, *one]
    raise ValueError(
        f"no array adjustment aligned the jump at depth {depth}, row {row!r}"
    )


def slow_acv_mammalian_boolean(truth_table: str) -> str:
    """Build a SLOW ACV MAMMALIAN program evaluating ``truth_table``.

    The program reads ``n`` digits with ``ACCEPT`` and prints the table entry
    for the combination it was given.  It is a decision tree of uniform depth
    ``n``, so a constant table still reads all ``n`` inputs.
    """
    n = _validate_truth_table(truth_table)
    if n == 0:
        return " ".join(_leaf([0], 0, int(truth_table)))
    return " ".join(_subtree(truth_table, n, 0, "", [0], 0, 0))
