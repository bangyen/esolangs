"""Boolean-function generator for SLOW ACV MAMMALIAN.

The language reads a byte with ``ACCEPT``, which appends ``byte ^ acc`` to
array 0 *whatever the pointer holds*, so nothing needs routing: the pointer
stays on array 0 for the whole program and the tree lives in code space,
built out of the one conditional the language has -- ``LEAPFROG`` jumps
exactly when the array's last element (the bit just read) is nonzero.

Everything here is a closed form; nothing is searched, measured, or
relaxed.  Two identities carry the construction, both verified against the
interpreter on 400 random machine states each and end to end over every
table through ``n == 3``:

``landing = start - 15``
    A read node is ``SEED*wrap EXCRETE SEED*j1 DIGEST SEED*16 DIGEST
    ACCEPT DIGEST LEAPFROG``.  Writing ``start`` for the array sum after
    the wrap and the ``EXCRETE`` and ``first = start + j1``, the 1-branch
    resumes at ``(first ^ ((first + 16) ^ (first + 17))) - (j1 + 16)``.
    :func:`_aim` picks the ``j1`` that puts ``first`` on an even value
    with bits 4-5 equal to ``01``: then the second seed run is exactly the
    ``+16`` that XORs down to the clean digit ``48`` for ``ACCEPT``,
    ``first + 16`` is even so the trailing XOR is ``1``, and the whole
    expression collapses to ``start - 15`` -- ``j1`` cancels.  A landing
    is therefore aimed *only* by raising the array sum, which stash chunks
    do in exact 256-token steps, and the residue games that used to need a
    256-candidate sweep per node reduce to one ``j1`` of at most 49.

``target = nonhead + b``
    ``LEAPFROG``'s target is ``acc - head - 1``, and ``DIGEST`` folds the
    whole array -- head included -- into the accumulator, so the head
    cancels out of any jump whose accumulator is a fresh ``DIGEST``: the
    trampoline ``SEED*u DIGEST EXCRETE DIGEST LEAPFROG`` resumes at
    exactly the sum of the non-head cells plus the byte ``b`` the
    ``EXCRETE`` appended, wherever the head happens to sit and whether or
    not the ``u`` run wrapped it.  ``u`` dials ``b`` to any value in
    ``1..255`` and a stash chunk moves the non-head sum by exactly 255, so
    for any target there is exactly one chunk count and one ``b`` -- an
    unconditional jump to an arbitrary token index, solved in one step.

The layout of a node is then::

    [stash chunks][read node][trampoline slot][dead pad][1-subtree][0-subtree]

The 1-branch jumps to ``start - 15``, where its subtree begins; the
0-branch falls through into the trampoline, which hops over the 1-subtree
to the 0-subtree.  The 1-subtree inherits the node's ballast -- its
entering sum is within a few dozen tokens of its own position -- and the
0-subtree enters through the trampoline whose own ballast serves the same
way, so no node starts poor and none needs the ``CONSUME`` shedding the
searching construction used to break the parent/child ballast lock: the
lock never forms, because ballast is spent where it stands instead of
being dropped and rebuilt.

What breaks the remaining circularity -- the chunk count depends on where
the 1-subtree ends, which depends on the chunk count -- is that the
trampoline is given a fixed-width *slot* sized from :func:`_widths` before
either subtree exists.  Everything in the slot after the trampoline's
``LEAPFROG`` is dead (the jump always fires: ``b >= 1``), and everything
between the slot and the landing is dead too (the 0-path leaves through
the trampoline, the 1-path lands past it), so the slot only has to be
*wide enough*, never exact.  The width comes from a per-depth cap
recurrence over this same construction; the two ``AssertionError``s below
are its alarms, and the exhaustive ``n <= 3`` sweep plus sampled ``n == 4``
and ``n == 5`` builds (0 misses, every row executed) are its evidence.

The tree is uniform depth ``n``: constant tables are not folded, because
the reads are the interface and every table has to consume all ``n``
inputs.
"""

from collections.abc import Sequence

from esolangs.tools.boolean.helpers import _ASCII_ZERO, _validate_truth_table

__all__ = ["slow_acv_mammalian_boolean"]

# The byte a stash chunk appends.  It is what raises the sum, and the sum is
# what puts a distant token index within a jump's reach, so the chunk buys
# the most reach per token by appending the largest byte there is.
_STASH_BYTE = 255

# The read node's second seed run.  The aim class fixes ``first & 48 == 16``,
# and XORing bits 4-5 from ``01`` to ``10`` is ``+16``, so this run is what
# lands the accumulator on the clean digit 48 -- it is not a free knob.
_J2 = 16

# The least a trampoline can hop.  Its byte ``b`` must be nonzero for the
# ``LEAPFROG`` to fire, and the non-head sum entering the trampoline is
# ``landing + 15`` exactly, so a 0-subtree is placed at least 16 tokens past
# the landing even when the 1-subtree is shorter than that -- the gap is
# dead code, reached by nothing.
_MIN_HOP = 16

# ``DIGEST PRONOUNCE EXCRETE LEAPFROG``: the fixed tail every leaf ends
# with, on top of at most 255 normalizing ``SEED``s.
_LEAF_TAIL = 4

# Slack :func:`_widths` adds over the arithmetic maxima.  The chunk-count
# and ``b`` solves are exact and the token maxima (257 per early chunk, 255
# for ``u``) are hard, so this only covers the formulas being off by a few
# tokens somewhere -- the asserts below would name the node if it ever ran
# out.  Measured over every build through ``n == 3``, the tightest slot had
# 22 tokens spare.
_SLOT_MARGIN = 8

# What a read node can cost beyond its prefix: a full 255-token wrap, the
# worst ``j1`` of 49 (the aim class repeats every 64 residues, 16 of them
# even with bits 4-5 ``01``), the fixed ``_J2`` run, and 7 one-token ops.
_NODE_MAX = 255 + 49 + _J2 + 7

# How far past its threshold a stop can land.  The last chunk moves the
# landing by at most 510 (a first chunk's count plus its append) while the
# threshold moves by at most 562 the other way (257 of prefix, a wrap
# rebound of 255, a ``j1`` swing of 49, and the ``EXCRETE`` byte), so one
# step never opens more than 1072 of dead pad.
_PAD_MAX = 1072

#: A machine state as the generator tracks it: array 0 and the accumulator.
type _State = tuple[list[int], int]


def _seeded(array: Sequence[int], count: int) -> list[int]:
    """``array`` after ``count`` ``SEED``s, which only move the head."""
    out = list(array)
    out[0] = (out[0] + count) % 256
    return out


def _stash_chunk(array: list[int], acc: int) -> tuple[list[str], list[int], int]:
    """``SEED*k DIGEST EXCRETE``, appending exactly ``_STASH_BYTE``.

    ``SEED`` advances the sum by one per token, and a head wrap drops it by
    256, so the sum's *low byte* advances by exactly one either way.  Only
    the low byte is spent -- ``EXCRETE`` appends ``acc % 256`` -- so the
    count solves in one step instead of a scan.  After the first chunk the
    accumulator is 0 and the sum's low byte settles, so from the third
    chunk on every count is 1: a chunk is then 3 tokens for 255 of reach.
    """
    count = (((acc % 256) ^ _STASH_BYTE) - sum(array)) % 256
    return (
        [*["SEED"] * count, "DIGEST", "EXCRETE"],
        [*_seeded(array, count), _STASH_BYTE],
        0,
    )


def _aim(start: int) -> int:
    """Return the seed count putting ``start + j1`` on the aim class.

    The class is even values whose bits 4-5 are ``01`` -- 16 residues out
    of every 256, at most 49 apart, so the count never exceeds 49 and the
    node's head stays far under the 255 a mid-run wrap would need.
    """
    offset = (start - _J2) % 64
    if offset <= 14:
        # Inside a class block; an odd ``start`` steps to the next even.
        return start % 2
    return 64 - offset


def _node(array: list[int], acc: int) -> tuple[list[str], _State, _State, int]:
    """One read node: tokens, the 0-exit, the 1-exit, and the landing.

    All four are arithmetic in the entering state.  The 0-branch falls
    through with ``acc == first`` and the bit 0 appended; the 1-branch
    jumps to ``start - 15`` with ``acc == first + 1`` and the bit 1
    appended.  Nothing about the exits depends on which ``j1`` the aim
    picked, which is what lets the landing be committed before either
    subtree exists.
    """
    wrap = (256 - array[0]) % 256
    opened = [*_seeded(array, wrap), acc % 256]
    start = sum(opened)
    j1 = _aim(start)
    first = start + j1
    tokens = [
        *["SEED"] * wrap,
        "EXCRETE",
        *["SEED"] * j1,
        "DIGEST",
        *["SEED"] * _J2,
        "DIGEST",
        "ACCEPT",
        "DIGEST",
        "LEAPFROG",
    ]
    loaded = _seeded(opened, j1 + _J2)
    return tokens, ([*loaded, 0], first), ([*loaded, 1], first + 1), start - 15


def _trampoline(
    array: list[int], acc: int, target: int
) -> tuple[list[str], list[int], int]:
    """Build an unconditional jump to token ``target``, plus its exit state.

    Chunks raise the non-head sum by exactly 255 each until ``target`` is
    within a byte's reach, and ``u`` is solved so the ``EXCRETE`` appends
    the one ``b`` that closes the rest: the final ``DIGEST`` folds the
    whole array into the cleared accumulator, so the jump resumes at the
    non-head sum plus ``b``, with the head cancelling out of
    ``acc - head - 1`` entirely.  ``b >= 1`` keeps the ``LEAPFROG`` firing
    (it is the array's last element), and the caller guarantees it by
    never asking for a hop shorter than ``_MIN_HOP``.
    """
    cur, val, tokens = list(array), acc, []
    while sum(cur) - cur[0] < target - 255:
        chunk, cur, val = _stash_chunk(cur, val)
        tokens += chunk
    hop = target - (sum(cur) - cur[0])
    if not 1 <= hop <= 255:  # pragma: no cover - the window solve is exact
        raise AssertionError(f"trampoline byte {hop} escaped 1..255")
    count = (((val % 256) ^ hop) - sum(cur)) % 256
    tokens += [*["SEED"] * count, "DIGEST", "EXCRETE", "DIGEST", "LEAPFROG"]
    out = [(cur[0] + count) % 256, *cur[1:], hop]
    return tokens, out, sum(out)


def _chunk_run(chunks: int) -> int:
    """Bound from above what ``chunks`` stash chunks cost in tokens.

    The first two counts are whatever the entering residues force (at most
    255 each); every later chunk is the settled 3-token form.
    """
    return 257 * min(chunks, 2) + 3 * max(0, chunks - 2)


def _widths(n: int) -> list[int]:
    """Per-level trampoline slot widths, from a cap recurrence.

    ``widths[d]`` is the slot for a node with ``d`` levels below it, sized
    against ``cap`` -- an upper bound on how wide a subtree of the *new*
    construction can be.  The recurrence mirrors the emitter: a subtree is
    its prefix (chunks solved against a threshold at most
    ``255 + 15 + prefix + _NODE_MAX + slot`` above the entering sum, since
    every entering sum is at least the node's own base), the node, the
    slot, the dead pad, and the two subtrees.  Everything is integer
    arithmetic; the asserts in :func:`_subtree` are the alarms if any line
    of it goes stale.
    """
    caps = [255 + _LEAF_TAIL]
    widths = [0]
    for d in range(1, n + 1):
        child = caps[d - 1]
        # The trampoline's shortfall is ``max(len(one), _MIN_HOP) - 15``
        # past an entering non-head sum of ``landing + 15``; chunks close
        # exactly 255 each and ``b`` closes the rest.
        span = max(child, _MIN_HOP) - 15
        hops = max(0, -(-(span - 255) // 255))
        slot = _chunk_run(hops) + 255 + _LEAF_TAIL + _SLOT_MARGIN
        widths.append(slot)
        # The node's own chunks: gains of 256 per chunk (one wrap chunk may
        # gain 0, hence the ``m - 3``) against a threshold growing 3 per
        # chunk once the counts settle.
        chunks = -(-(255 + 15 + 514 + _NODE_MAX + slot + 768) // 253)
        caps.append(
            _chunk_run(chunks)
            + _NODE_MAX
            + slot
            + _PAD_MAX
            + max(child, _MIN_HOP)
            + child
        )
    return widths


def _leaf_seeds(array: list[int], acc: int, bit: int) -> int:
    """``SEED``s bringing the accumulator onto the digit's residue class.

    Only ``acc % 256`` is ever printed, so this is the same one-step solve
    the stash chunk uses rather than a scan over 256 counts.
    """
    return (((acc % 256) ^ (_ASCII_ZERO + bit)) - sum(array)) % 256


def _leaf(array: list[int], acc: int, bit: int) -> list[str]:
    """Print the table entry, then halt.

    ``EXCRETE`` appends the printed byte (48 or 49, so nonzero: ``LEAPFROG``
    fires) and clears the accumulator, which makes the jump target
    ``0 - head - 1``.  That is negative, which the interpreter halts on.
    """
    count = _leaf_seeds(array, acc, bit)
    return [*["SEED"] * count, "DIGEST", "PRONOUNCE", "EXCRETE", "LEAPFROG"]


def _entry(table: str, row: str) -> int:
    """Read the table's value on the path ``row``."""
    return int(table[int(row, 2) if row else 0])


def _subtree(
    table: str,
    n: int,
    depth: int,
    row: str,
    array: list[int],
    acc: int,
    base: int,
    widths: list[int],
) -> list[str]:
    """Build the subtree rooted here, knowing it starts at token ``base``."""
    if depth == n:
        return _leaf(array, acc, _entry(table, row))

    slot = widths[n - depth]
    prefix: list[str] = []
    cur, val = list(array), acc
    while True:
        tokens, fell, taken, landing = _node(cur, val)
        if landing >= base + len(prefix) + len(tokens) + slot:
            break
        # Not enough sum to clear the slot: stash another 255.  This always
        # ends -- a chunk moves the landing by 256 (a rare head-wrap chunk
        # by 0) while the threshold moves by 3 plus a bounded sawtooth --
        # and every entering sum is at least ``base``, so the chunk count
        # stays a handful rather than tracking the program's size.
        chunk, cur, val = _stash_chunk(cur, val)
        prefix.extend(chunk)

    node_end = base + len(prefix) + len(tokens)
    one = _subtree(table, n, depth + 1, f"{row}1", *taken, landing, widths)
    target = landing + max(len(one), _MIN_HOP)
    hop, out_array, out_acc = _trampoline(*fell, target)
    if len(hop) > slot:  # pragma: no cover - alarm for a stale _widths
        raise AssertionError(
            f"trampoline of {len(hop)} tokens overflowed its {slot}-token slot"
        )
    dead = landing - node_end - len(hop)
    if dead < 0:  # pragma: no cover - alarm for a stale _widths
        raise AssertionError(f"the 1-subtree landed {-dead} tokens into the slot")
    zero = _subtree(table, n, depth + 1, f"{row}0", out_array, out_acc, target, widths)
    return [
        *prefix,
        *tokens,
        *hop,
        *["SEED"] * dead,
        *one,
        *["SEED"] * (target - landing - len(one)),
        *zero,
    ]


def slow_acv_mammalian_boolean(truth_table: str) -> str:
    """Build a SLOW ACV MAMMALIAN program evaluating ``truth_table``.

    The program reads ``n`` digits with ``ACCEPT`` and prints the table entry
    for the combination it was given.  It is a decision tree of uniform depth
    ``n``, so a constant table still reads all ``n`` inputs.
    """
    # ``_validate_truth_table`` refuses a one-entry table, so the tree
    # always has at least one level to read.
    n = _validate_truth_table(truth_table)
    return " ".join(_subtree(truth_table, n, 0, "", [0], 0, 0, _widths(n)))
