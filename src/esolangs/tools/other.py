"""Boolean-function generators for languages in the ``other`` category."""

# laserfuck, streetcode and ztoalc_l each own a file because their
# construction (a grid layout or a program search) dwarfs the rest of the
# category; they are re-exported here so this module stays the import site
# the package and tests already use.

from itertools import pairwise

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    best_input_order,
    constant_span_test,
    essential_inputs,
    read_at,
)
from esolangs.tools.laserfuck import laserfuck
from esolangs.tools.streetcode import streetcode
from esolangs.tools.ztoalc_l import ztoalc_l

__all__ = [
    "bit_tilde",
    "clockwise",
    "container",
    "forbin",
    "laserfuck",
    "streetcode",
    "taglate",
    "three_x",
    "ztoalc_l",
]

# Closed-form 3x constant encodings.  Every integer is built from the literal
# 3 with the ``x`` op (which replaces the top three items ``a, b, c``, c on
# top, with ``(c-b)//a``).  The three base-3 digits are:
_ZERO = "333x"  # (3-3)//3 = 0
_ONE = "3333x3x"  # (3-0)//3 = 1
_TWO = _ONE + _ONE + "3x"  # (3-1)//1 = 2

# From [v], ``push X # push Y x`` leaves [(Y-v)//X], so with X=-1/3 and
# Y=-d/3 it maps v -> (-d/3 - v)/(-1/3) = 3v + d.  These are the two fixed
# rationals (and the d=0 case, which is just 0):
_NEG_THIRD = "3" + _ONE + _ZERO + "x"  # (0-1)//3 = -1/3
_NEG_TWO_THIRDS = "33" + _ONE + "x"  # (1-3)//3 = -2/3
_DIGIT = (_ZERO, _ONE, _TWO)
_NEG_DIGIT = (_ZERO, _NEG_THIRD, _NEG_TWO_THIRDS)


def _const(n: int) -> str:
    """3x code pushing ``n`` on a clean stack, for any integer ``n``.

    ``n`` is written in base 3 and its digits are processed most significant
    first: ``v`` starts as the leading digit and each following digit ``d``
    applies the affine map ``v -> 3v + d`` via one ``x`` (see ``_NEG_THIRD``).
    The result is a closed-form program of ``O(log_3 n)`` length leaving
    exactly ``[n]`` on the stack.
    """
    if n <= 2:
        return _DIGIT[n]
    digits = []
    while n:
        digits.append(n % 3)
        n //= 3
    prog = _DIGIT[digits[-1]]
    for d in reversed(digits[:-1]):
        prog += _NEG_THIRD + "#" + _NEG_DIGIT[d] + "x"
    return prog


def three_x(truth_table: str) -> str:
    """Build a 3x program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    3x reads an integer with ``?`` and has no direct boolean literals or
    conditionals, so the generator builds a decision tree with variables:

    - each ``?`` reads one input bit and stores it in a variable (the
      cheapest names after 0 and 3);
    - a ``( ... )`` loop runs while its guard is nonzero: the guard value is
      popped into a trash variable (0), the body stores the table entry into
      the result variable (3), and a sentinel zero exits the loop.

    The result variable defaults to the majority table value (so the
    ``( ... )`` loop emits no override when every row matches), and only the
    input combinations whose table entry differs from the default get an
    override block.  Each override's ``( ... )`` guard leaves the stack
    balanced via the trash pop, so arbitrary ``n`` works.

    **The tree splits on its inputs in whichever order emits the shortest
    program** (:func:`~esolangs.tools.helpers.best_input_order`).
    The reorder is spelled in the *store targets* rather than in the tree:
    ``?`` consumes the stream in order, but each read may store into any
    variable, so reading stream input ``i`` into the name the tree tests at
    depth ``perm.index(i)`` reorders the splits while consuming the input
    stream exactly as before.

    That makes the reorder **free of any cost the search cannot see**.  The
    read block stores each name exactly once whatever the order, so its
    length never changes, and the tree is byte-identical to the one the
    permuted table produces -- unlike a generator that walks to its inputs
    (Circlefuck) or has to hoist them first (S*bleq, BrainIf), where the
    screen is respectively an over- and an under-estimate.  Here the screen
    figure is exact: 4.5% at n=3 (146 of 256 tables improved), 5.4% at n=4.
    """
    return best_input_order(truth_table, _three_x_ordered)


def _three_x_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's 3x program; see :func:`three_x`.

    ``perm[k]`` is the stream input the tree tests at depth ``k``, so stream
    input ``i`` is stored into ``input_vars[perm.index(i)]`` and the tree
    itself is unchanged.
    """
    n = _validate_truth_table(truth_table)

    # Variable allocation: var 0 is the loop-trash (its constant, 333x, is
    # short and emitted twice per guard), var 3 is the result (its constant
    # is the single char `3`, emitted once per table entry), and the inputs
    # live in the cheapest remaining names by actual constant length (the
    # base-3 encodings are non-monotonic: 15 is cheaper than 13).  Deep tree
    # levels occur exponentially more often in the emitted program, so the
    # cheapest name goes deepest.  Reversing the length order makes the name
    # cost a geometric sum rather than repeating the longest name at half the
    # nodes.  Which input lands at which depth is what ``best_input_order``
    # searches over.
    trash = _const(0) + "#v"  # pop the stack top into variable 0
    result = 3
    used = {0, 3}
    input_vars = sorted(
        (v for v in range(3 + n) if v not in used),
        key=lambda v: len(_const(v)),
    )[:n][::-1]

    def store(var: int) -> str:
        return _const(var) + "#v"  # var = stack top, stack ends empty

    def read(var: int) -> str:
        return _const(var) + "^"

    def not_bit() -> str:
        return _ONE + "#" + _ONE + "x"  # from [b] leave [1-b]

    def guard(i: int, body: str) -> str:
        """If bit i is 1, run ``body``; leaves the stack balanced."""
        return read(i) + "(" + trash + body + _ZERO + ")" + trash

    def guard_not(i: int, body: str) -> str:
        """If bit i is 0, run ``body``; leaves the stack balanced."""
        return read(i) + not_bit() + "(" + trash + body + _ZERO + ")" + trash

    # A table that ignores some of its inputs is a smaller table, and this
    # tree does not fold it away on its own: it prunes only the rows that
    # *differ from the default*, which for a one-dependency table is still
    # half of them, each carrying a full-depth guard chain.  Reducing to the
    # essential inputs collapses those to one guard.  The reads stay in
    # stream order -- every input is still ``?``-read and stored, which is
    # the interface -- and an ignored one lands in a variable the tree never
    # reads.
    essential = essential_inputs(truth_table, n) or [0]
    if len(essential) < n:
        table = read_at(truth_table, essential, n)
        width = len(essential)
    else:
        table, width = truth_table, n

    # Reads run in stream order; only the store target moves.  Stream input
    # ``i`` goes into the name the tree tests at depth ``perm.index(i)``.
    # A reduced tree tests only ``width`` names, so the ignored inputs take
    # the leftover ones; ``perm`` is a permutation of all ``n`` either way.
    depth_of = {stream: depth for depth, stream in enumerate(perm)}
    prog = "".join("?" + store(input_vars[depth_of[i]]) for i in range(n))

    # Default the result to the majority value so only the minority rows
    # need an override block (combos matching the default are skipped).
    default = "1" if table.count("1") >= table.count("0") else "0"
    prog += (_ONE if default == "1" else _ZERO) + store(result)

    # One decision tree instead of an independent guard chain per differing
    # combo: rows that share a bit prefix share the guards for that prefix,
    # amortizing the ~19-char guard scaffolding across them.  Each guard
    # leaves the stack balanced, so both branches concatenate safely inside
    # their parent's body, and whole subtrees that match the default are
    # pruned.
    def override(combo: int) -> str:
        return (_ONE if table[combo] == "1" else _ZERO) + store(result)

    # ``truth_table`` is already the *permuted* table when the reorder
    # wrapper calls this, so ``essential`` is in the tree's own coordinates:
    # entry ``s`` names the depth the unreduced tree would have tested, and
    # the bit for that depth sits in ``input_vars[essential[s]]``.  Going
    # back through ``depth_of`` would mix stream and tree coordinates, which
    # agrees only when the essential set is contiguous from 0 -- gapped sets
    # like ``[0, 2]`` are exactly where that mismatch shows up.
    slot_var = [input_vars[s] for s in essential]

    def build(rows: list[int], depth: int) -> str:
        if not rows:
            return ""
        if depth == width:
            return override(rows[0])  # rows are pruned, so it differs from default
        bit = width - 1 - depth
        rows1 = [r for r in rows if (r >> bit) & 1]
        rows0 = [r for r in rows if not (r >> bit) & 1]
        sub1 = build(rows1, depth + 1)
        sub0 = build(rows0, depth + 1)
        return (guard(slot_var[depth], sub1) if sub1 else "") + (
            guard_not(slot_var[depth], sub0) if sub0 else ""
        )

    differing = [c for c in range(2**width) if table[c] != default]
    prog += build(differing, 0)

    prog += read(result) + "!"
    return prog


def _reorder_tt(tt: str, n: int) -> str:
    """Reorder truth table entries into the slot order the reduces expect.

    Each entry sits in a value slot ``[0, s_i, 0, s_j, ...]``; an even
    reduce must be able to drop an entire contiguous run of slots without
    splitting a pair.  Sorting the input index ``i`` by ``(-(i >> 1),
    i & 1)`` puts the 1-group of the current input first, then the 0-group,
    with the two sub-cases of the next input adjacent inside each group.
    Odd-reduce levels (which branch the other way) then re-apply the same
    ordering, so the sort key serves both.
    """
    indices = sorted(range(2**n), key=lambda i: (-(i >> 1), i & 1))
    return "".join(tt[i] for i in indices)


def _even_reduce(pairs: int, level: int, n: int) -> str:
    """Even-reduction block: select half the value pairs, keep all inputs.

    The queue holds ``2*pairs`` value slots ``[0, s0, 0, s1, ...]``, then
    two 48s, then the ``n`` input chars.  The ``rot`` rotation brings the
    next input to the front; ``gy ... gz`` branches on it so the ``e^pairs``
    strides past the half of the value slots the input rejects; ``e^ahead``
    skips the untouched half and ``f^pairs`` drops it.  Every input stays on
    the queue, so the level that follows still sees all ``n`` of them.
    """
    processed = level
    ahead = n - level
    total = n
    rot = 2 * pairs + 2 + processed
    return (
        "e" * rot
        + "gy"
        + "e" * pairs
        + "gz"
        + "e" * ahead
        + "f" * pairs
        + "gy"
        + "e" * (total + 2)
        + "gz"
    )


# Final odd-reduce block: the committed n==2 pattern.  Given the 8-cell
# queue [0, v0, 0, v1, 48, 48, prev, curr] (v0/v1 the two candidate values,
# prev/curr the two remaining inputs), it rotates curr and prev to the front,
# drops the candidate the inputs reject, adds the surviving value to one of
# the two 48s (48 + bit), and prints it with ``i``.
_SEL1_N2: str = (
    "e" * 7
    + "gy"
    + "e" * 3
    + "gz"
    + "e" * 3
    + "gy"
    + "e" * 3
    + "gz"
    + "ff"
    + "gy"
    + "e" * 4
    + "gz"
    + "e"
    + "a"
    + "e" * 4
    + "i"
)


def _build_padded_tt(truth_table: str, n_effective: int) -> str:
    """Pad a ``2**(n_effective - 1)``-entry truth table to ``n_effective`` bits.

    Odd ``n`` is computed with ``n_effective = n + 1`` inputs whose leading
    (ghost) digit is always 0.  The real table covers the ghost=0 half; the
    entries the ghost=1 would select are padded with 0 so the never-taken
    rows stay harmless.
    """
    half = 2 ** (n_effective - 1)
    return truth_table.ljust(half * 2, "0")


def _odd_reduce(pairs: int, level: int, n: int) -> str:
    """Odd-reduction block: retire one input, reduce, keep the rest.

    ``level`` is the 0-based reduce level (odd here: 1, 3, ...).  The queue
    holds ``2*pairs`` value slots ``[0, s0, 0, s1, ...]``, then two 48s,
    then the ``n`` input chars.  Unlike the even reduce, the odd level
    branches on a *retired* (previous) input whose bit has already been
    used, so ``e^rot`` brings that input to the front and the block runs
    ``zero`` (``gy j e^(qlen-1) gz``) to fold it away, ``swap`` (``e gy j
    e^(qlen-2) j gz``) to encode the current input as the ghost cell the
    even-reduce branches on, and ``bring`` (``e^(qlen-1)``) to put the
    value slots back at the front before ``er`` runs the even-reduce body.

    The ZS adds an extra ghost cell at the front, so the even-reduce body
    uses ``ahead = n - level + 1`` instead of ``n - level``.  No input is
    popped; the final ``f^pairs`` in ``er`` drops only the rejected value
    slots.
    """
    processed = level
    ahead = n - level + 1  # +1 for the ghost cell added by the swap
    total = n
    qlen = 2 * pairs + 2 + total
    rot = 2 * pairs + 2 + (processed - 1) if processed > 0 else 0
    zero = "gy" + "j" + "e" * (qlen - 1) + "gz"
    swap = "e" + "gy" + "j" + "e" * (qlen - 2) + "j" + "gz"
    bring = "e" * (qlen - 1)
    er = (
        "gy"
        + "e" * pairs
        + "gz"
        + "e" * ahead
        + "f" * pairs
        + "gy"
        + "e" * (total + 2)
        + "gz"
    )
    return "e" * rot + zero + swap + bring + er


def _taglate_reduced_table(truth_table: str, n: int, used: list[int]) -> str:
    """Rewrite the function over just the inputs in ``used``."""
    width = len(used)
    return "".join(
        truth_table[
            sum(
                1 << (n - 1 - i)
                for slot, i in enumerate(used)
                if (row >> (width - 1 - slot)) & 1
            )
        ]
        for row in range(2**width)
    )


def taglate(truth_table: str) -> str:
    r"""Build a Taglate program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    ``n == 1`` reads the single input with ``h`` and computes the affine
    combination ``base + bit * coeff`` with the ``b``/``c``/``a`` queue
    arithmetic, then prints it.

    For ``n >= 2`` the program is ``seed\\n<commands>``.  The seed holds
    ``n_effective`` literal ``'1'``s (``n_effective - 1`` leading, one
    trailing) around a run of ``'0'``s; the prefix of ``h``/``e``/``b``/
    ``d``/``j`` commands reads ``n_effective`` inputs and interleaves the
    (reordered) truth-table bits into ``[0, s0, 0, s1, 0, s2, ...]`` value
    slots, followed by two 48s and the inputs.  Odd ``n`` prepends a fake
    zero input (ghost digit) so the slot stride lands on a separator, and
    pads the table to ``n_effective = n + 1`` inputs.

    The command list alternates even-reduce blocks (select half the
    value slots on an input bit, keep all inputs) and odd-reduce blocks
    (retire the previous input, swap the current one in, even-reduce).
    Neither reduce pops inputs; ``e^6 f^(n_effective - 2) e^2`` reshapes
    the queue into the 8-cell ``[0, v0, 0, v1, 48, 48, prev, curr]``
    layout, and ``_SEL1_N2`` selects between the last two candidate
    values on the two remaining inputs and prints ``48 + bit``.

    **A table that ignores some of its inputs is emitted as the smaller
    table.**  Nothing here costs anything per *row* -- a one and a zero are
    both two characters (``bd``/``bb``) -- but almost everything costs per
    *input*, and the seed alone is ``2**(n_eff + 2)`` cells, so dropping one
    input drops a whole tier: a constant table goes from 451 characters to
    21, and ``11110000`` (which depends only on its first input) to 21 as
    well.  The ignored inputs are still read, then discarded: ``h`` appends
    the character to the queue's tail, ``e`` repeated once per queued cell
    rotates it back to the front, and ``f`` drops it, leaving the queue
    exactly as it was so the reduces' positional arithmetic is undisturbed.
    The rotation count is the queue length at that point, which before any
    command has run is the seed's -- computed, not searched.

    A discard can also go *between* the reduced program's reads.  After its
    ``j``-th ``h``, the queue has ``len(seed) + j`` cells; ``h`` then appends
    the ignored input, so rotating that many times brings the new tail cell
    to the front for ``f``.  That restores the exact queue the next command
    expects, allowing a gapped set such as inputs 0 and 2.  An odd-sized
    dependency set would make the reduced program ghost-pad itself and expect
    an input the stream does not carry, so the set is widened by one adjacent
    ignored input to keep it even.
    """
    n = _validate_truth_table(truth_table)

    # A table that ignores some of its inputs is really a smaller table, and
    # taglate's cost is almost all fixed overhead scaled by the input count
    # -- the seed alone is ``2**(n_eff + 2)`` cells -- so dropping one input
    # drops a whole tier.  Emit the reduced table's program and read the
    # ignored inputs anyway, discarding each with ``h``/``e``-rotate/``f``,
    # which leaves the queue exactly as it was so the reduces' positional
    # arithmetic is undisturbed.
    #
    used = essential_inputs(truth_table, n)
    # A constant table depends on nothing, so it reduces to the smallest
    # valid table there is -- a one-input constant, never the length-1
    # table, which is not a valid shape.
    if not used and n > 1:
        used = [0]
    # An odd-sized dependency set would make the *reduced* program
    # ghost-pad itself and expect an input the stream does not carry, so
    # widen it by one adjacent ignored input to keep it even.
    if len(used) % 2 == 1 and len(used) > 1:
        if used[-1] + 1 < n:
            used = [*used, used[-1] + 1]
        elif used[0] > 0:
            used = [used[0] - 1, *used]
    if 0 < len(used) < n and (len(used) % 2 == 0 or len(used) == 1):
        reduced = _taglate_reduced_table(truth_table, n, used)
        seed, commands = taglate(reduced).split("\n", 1)
        discard = "h" + "e" * len(seed) + "f"
        # Odd ``n`` above 1 is called with a leading ghost digit, which is
        # one more input to read and throw away before the real ones.
        ghost = 1 if n % 2 == 1 and n > 1 else 0
        leading = used[0] + ghost
        reads = commands.split("h")
        parts = [reads[0] + "h"]
        for read, (before, after) in enumerate(pairwise(used), start=1):
            between = "h" + "e" * (len(seed) + read) + "f"
            parts.append(between * (after - before - 1))
            parts.append(reads[read] + "h")
        parts.append(reads[-1])
        trailing = n - used[-1] - 1
        return seed + "\n" + discard * leading + "".join(parts) + "h" * trailing

    if n == 1:
        base = _ASCII_ZERO + int(truth_table[0])
        coeff = (int(truth_table[1]) - int(truth_table[0])) % 65536
        seed = "0" + chr(coeff) + chr(base)
        return seed + "\n" + "h" + "e" * 3 + "b" + "e" * 2 + "ca" + "i"

    # For odd n, prepend a fake zero-input (ghost) to make the stride land
    # on a separator.  n_effective is the number of h-reads and levels.
    if n % 2 == 1 and n > 1:
        n_eff = n + 1
        full_tt = _build_padded_tt(truth_table, n_eff)
    else:
        n_eff = n
        full_tt = truth_table

    seed = "1" * (n_eff - 1) + "0" * (2 ** (n_eff + 2) + 2) + "1"

    ordered = _reorder_tt(full_tt, n_eff)
    selectors = "".join("bd" if c == "1" else "bb" for c in ordered)

    prefix = (
        "he" * (n_eff - 1)
        + "h"
        + selectors
        + "ee"
        + "b" * n_eff
        + "e" * (2 ** (n_eff + 1) + 2)
        + "j" * n_eff
    )

    select_parts: list[str] = []
    for level in range(n_eff - 1):
        pairs = 2 ** (n_eff - level)
        if level % 2 == 0:
            select_parts.append(_even_reduce(pairs, level, n_eff))
        else:
            select_parts.append(_odd_reduce(pairs, level, n_eff))

    if n_eff > 2:
        # Drop the first n_eff-2 already-used inputs, then rotate the
        # remaining two inputs so the queue matches the 8-cell [0, w0, 0,
        # w1, 48, 48, prev, curr] layout that the committed n=2 odd
        # selector (_SEL1_N2) expects.
        select_parts.append("e" * 6 + "f" * (n_eff - 2) + "e" * 2)
    select_parts.append(_SEL1_N2)

    result: str = seed + "\n" + prefix + "".join(select_parts)
    return result


# Cells in a Clockwise leaf: 'S', the seven ';' that print the answer digit
# with the '+' that set their parity, and the 'S+?' exit.  Both digits fit
# in this height -- '0' pads with one extra 'S' -- so the two leaves of a
# node always end on the same row.
_CLOCKWISE_LEAF = 14

# Rows one level of the tree spends: 'S', seven '.', and the '?' that turns.
_CLOCKWISE_LEVEL = 9


def clockwise(truth_table: str, width: int | None = None) -> str:
    """Build a Clockwise program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    program prints the result as the ASCII digit ``'0'`` or ``'1'``.
    Without a width, the compact form compares the flat tree with one partial
    stack bounded to eight columns per input and keeps the shorter.  This is
    two named linear builds, not a search over stack depths.  ``width`` asks
    for a column count; the tree stacks as much of itself as it needs to meet
    one, and a width under the floor returns the narrowest program rather than
    refusing.

    The program is a decision tree in a closed ring.  ``S`` zeroes the
    accumulator and seven ``.`` reads consume a ``0``/``1`` input char's seven
    bits, leaving its value bit in the accumulator.  At each node a ``?``
    turns the pointer by ``acc`` quarter-turns, so a zero bit continues down
    the spine while a one bit turns aside into a column of its own; three
    ``R`` in an L pattern turn it back down into that column.

    A leaf prints the answer's seven bits with ``;``, which emits ``acc % 2``,
    so a ``+`` before a ``;`` flips the parity into the bit that position
    needs.  Printing the ASCII digit rather than the bare bit costs almost
    nothing here: ``'0'`` is ``0110000`` and ``'1'`` is ``0110001``, so the
    two leaves differ by a single ``+``.  The leaf then resets and counts up
    to one (``S+``) so the exit ``?`` sees ``acc == 1`` whatever it printed,
    and turns left along its own row; an ``S`` just left of each exit drops
    passing paths back to zero so they do not turn on another leaf's exit.

    Every exit row ends at column 0 on a ``!``, which turns a path that
    arrives with a zero accumulator up the left edge, and a ``+`` one row
    above puts the accumulator back to one -- so a path climbing the edge
    passes the exits above it without turning on their ``!``.  That is what
    lets leaves finish on *different* rows: the ring closes through column 0
    rather than through one shared bottom row.

    Two ways the tree separates its paths, and the width picks between
    them.  A node can send its one-branch to a column of its own, which
    costs the columns that branch displaces -- the classic layout, and the
    reason an unstacked tree grows as ``2 ** (n + 1)``.  Or it can send it
    one column left and *stack* the two subtrees, the zero-branch falling
    down its own column through the one-branch's rows to start below them.
    Stacking costs one column per level instead of ``2 ** (n - bit)``, and
    pays for it in rows: the subtree below a stacked node is written twice
    over, so each stacked level doubles the program's height.

    The shallow levels displace furthest, so those are the ones stacked
    first: ``width`` fixes the smallest number of levels that brings the
    grid inside it, and the rest of the tree lays out flat.

    A subtree whose rows all agree stops branching, which narrows the ring:
    a node displaces only as far as its zero-branch actually spans, and a
    folded node spans one column.

    Two things the fold does *not* get to do.  It cannot drop the reads:
    Clockwise reads inside the tree, seven ``.`` per level, so a folded
    column still spends them (and an ``S`` where the ``?`` would have been,
    keeping the two leaves of a node the same height).  And it cannot narrow
    past the hoist: the root's seven reads sit on row 0 left of the corner
    ``R``, which retires seven rows but needs seven free columns, so an
    unasked-for width floors at what the hoist needs.  A width that is
    asked for may go under it -- the request is the point.
    """
    n = _validate_truth_table(truth_table)
    constant_span = constant_span_test(truth_table)

    def constant(bit: int, combo: int) -> bool:
        """Whether every row this subtree covers agrees.

        Rows split most-significant-first, so the subtree entered at
        ``bit`` with prefix ``combo`` covers the contiguous run of
        ``2 ** (n - bit)`` rows starting at ``combo << (n - bit)``.
        """
        span = 2 ** (n - bit)
        start = combo << (n - bit)
        return constant_span(start, start + span)

    def leafy(bit: int, combo: int) -> bool:
        """Whether this subtree stops here, either at ``n`` or on a fold."""
        return bit == n or (bit > 0 and constant(bit, combo))

    shapes: dict[tuple[int, int, int], tuple[int, int]] = {}

    def shape(bit: int, combo: int, stacked: int) -> tuple[int, int]:
        """Report the columns and rows this subtree needs, spine on the right.

        A leaf, folded or not, is one column: a folded one pads its skipped
        levels to the rows they would have spent, so the two subtrees of a
        node are always the same height and their leaves share a row.

        A stacked node spans one more column than its one-branch (or the
        three its own turn needs, whichever is wider) and as many rows as
        both subtrees together.  A flat one displaces its one-branch clear
        of the zero-branch's span -- two columns at the least, so no leaf
        sits directly left of another and the ``S`` before an exit has a
        cell of its own -- and the two subtrees share the rows.
        """
        key = (bit, combo, stacked)
        if key not in shapes:
            if leafy(bit, combo):
                shapes[key] = (1, _CLOCKWISE_LEVEL * (n - bit) + _CLOCKWISE_LEAF)
            else:
                one = shape(bit + 1, (combo << 1) | 1, stacked)
                zero = shape(bit + 1, combo << 1, stacked)
                if bit < stacked:
                    shapes[key] = (
                        max(3, one[0] + 1, zero[0]),
                        _CLOCKWISE_LEVEL + one[1] + zero[1],
                    )
                else:
                    step = max(2, zero[0])
                    shapes[key] = (
                        step + max(1, one[0] - 1) + 1,
                        _CLOCKWISE_LEVEL + max(one[1], zero[1]),
                    )
        return shapes[key]

    def spine(stacked: int) -> int:
        """Return the root's column with ``stacked`` levels stacked.

        Column 0 belongs to the ring, so the tree starts one column in.
        The hoist needs seven free columns left of the root and pays for
        them with seven rows, which is the better trade whenever the width
        was not asked for.
        """
        root = shape(0, 0, stacked)[0]
        if 2 ** (n + 1) >= 8 and (width is None or width >= 9):
            root = max(root, 8)
        return root

    # The shallow levels are the expensive ones -- a node at ``bit``
    # displaces ``2 ** (n - bit)`` columns -- so stacking starts at the
    # root and takes as few levels as the width needs.  A width under the
    # floor stacks everything, which is the narrowest tree there is.
    stacked = 0
    if width is not None:
        for count in range(n + 1):
            stacked = count
            if spine(count) + 1 <= width:
                break

    root = spine(stacked)
    # What the hoist's floor added over the tree's own span.  The turns are
    # relative, so the tree's absolute column never matters -- but its rows
    # are trimmed, so a cell further right costs a character.  Spending the
    # slack on the root's own displacement slides the whole one-branch back
    # against the left edge and leaves the gap between the two subtrees,
    # where the zero-branch's columns already set every row's length.
    slack = root - shape(0, 0, stacked)[0]
    hoist = root >= 8
    # Hoisting the root's reads onto row 0 retires seven rows of spine, so
    # the tree starts that much higher and every row below rides up with it.
    shift = 7 if hoist else 0

    cells: dict[tuple[int, int], str] = {}
    exits: list[tuple[int, int]] = []

    def place(node: tuple[int, int], ch: str) -> None:
        """Write ``ch`` at ``node``, refusing to land on an occupied cell.

        The geometry above is what keeps two cells apart; this is what
        says so.  A Clockwise cell acts only on the pointer standing on it,
        so an overwrite is the whole of what a bad layout can do to the
        grid -- and a program that silently lost a turn would be wrong in a
        way only a run of every input combination would find.
        """
        if node in cells:
            raise AssertionError(f"two cells at {node}: {cells[node]!r} and {ch!r}")
        cells[node] = ch

    def leaf(x: int, y: int, combo: int) -> None:
        """Print the answer at ``(x, y)`` and leave by the row it ends on."""
        # Emit the answer as the ASCII digit rather than as the raw bit.
        # Seven ';' print one bit each, most significant first, and each
        # prints acc % 2 -- so a '+' before a ';' is what flips the parity
        # into the bit that position needs.  '0' is 0110000 and '1' is
        # 0110001, which differ only in the last bit, so the two leaves are
        # the same shape apart from one '+'.
        result = int(truth_table[combo])
        code = "S"
        acc = 0
        for bit in format(_ASCII_ZERO + result, "07b"):
            if acc % 2 != int(bit):
                code += "+"
                acc += 1
            code += ";"
        # A '?' turns by acc quarter-turns and must see exactly 1 to turn
        # left onto its exit row.  The accumulator is 2 or 3 by now
        # depending on the digit, so reset and count up to 1 rather than
        # tracking it: 'S+' is uniform where a bare '+' would not be.  The
        # extra 'S' pads the shorter leaf so both are _CLOCKWISE_LEAF cells,
        # which is what keeps the two leaves of a node the same height.
        code += "S" * (_CLOCKWISE_LEAF - len(code) - 2) + "+?"
        for i, ch in enumerate(code):
            place((x, y + i), ch)
        exits.append((x, y + _CLOCKWISE_LEAF - 1))

    def build(bit: int, x: int, y: int, combo: int) -> None:
        """Lay the subtree for ``combo`` at ``bit``, spine head at ``(x, y)``."""
        if leafy(bit, combo):
            # Every row below here agrees, so the remaining bits cannot
            # change the answer and this column needs no more branching.
            # The reads are not optional, though: a program whose input
            # count depended on its table would desync a caller feeding
            # several from one stream, and unlike the tape generators
            # clockwise reads *inside* the tree.  So the skipped levels
            # still spend their ``S`` and seven ``.`` -- everything but
            # the ``?`` that would have turned the pointer.  The ninth row
            # is padded with an ``S`` -- a no-op on an accumulator the
            # reads leave at 0 or 1 -- so the column still ends where an
            # unfolded one would, and a node's two leaves stay level.
            for level in range(n - bit):
                place((x, y + _CLOCKWISE_LEVEL * level), "S")
                for i in range(7):
                    place((x, y + _CLOCKWISE_LEVEL * level + 1 + i), ".")
                place((x, y + _CLOCKWISE_LEVEL * level + 8), "S")
            leaf(x, y + _CLOCKWISE_LEVEL * (n - bit), combo << (n - bit))
            return
        if bit == 0 and hoist:
            # The seven reads sit on row 0, left of the corner ``R``; the
            # node's ``?`` is all that is left of its spine.
            for i in range(7):
                place((x - 7 + i, 0), ".")
        else:
            place((x, y), "S")
            for i in range(7):
                place((x, y + 1 + i), ".")
        place((x, y + 8), "?")
        one = shape(bit + 1, (combo << 1) | 1, stacked)
        zero = shape(bit + 1, combo << 1, stacked)
        # A stacked node displaces a single column and drops its
        # zero-branch below the one-branch's rows; a flat one displaces
        # past the zero-branch's span and the two share the rows.
        step = 1 if bit < stacked else max(2, zero[0])
        xn = x - step - (slack if bit == 0 else 0)
        # b=1: '?' turns the pointer aside, then three R's turn it down
        place((xn, y + 8), " ")
        place((xn - 1, y + 8), "R")
        place((xn - 1, y + 7), "R")
        place((xn, y + 7), "R")
        build(bit + 1, xn, y + 9, (combo << 1) | 1)
        below = one[1] if bit < stacked else 0
        # b=0: fall down this column, past the one-branch when it stacks
        build(bit + 1, x, y + 9 + below, combo << 1)

    build(0, root, 1 - shift, 0)

    for x, y in exits:
        # Drop a passing path back to zero so it does not turn on the exit
        # of a leaf further left along the same row.
        place((x - 1, y), "S")
    for y in sorted({y for _, y in exits}):
        # The ring closes up column 0: '!' takes a path that arrives with a
        # zero accumulator, and the '+' above it puts the accumulator back
        # so the climb passes every exit above without turning.
        place((0, y), "!")
        place((0, y - 1), "+")
    place((root, 0), "R")

    height = max(y for _, y in cells) + 1
    span = max(x for x, _ in cells) + 1
    grid = [[" "] * span for _ in range(height)]
    for (x, y), ch in cells.items():
        # ``span`` and ``height`` are derived from these very cells, so the
        # test holds for every one of them; it stays as the guard that keeps
        # a future caller's stray coordinate from writing outside the grid.
        if 0 <= x < span and 0 <= y < height:  # pragma: no branch - see above
            grid[y][x] = ch
    # The grid is a fixed-size rectangle of blanks that the cells are painted
    # into, so a row's trailing filler is never reached; the interpreter pads
    # short rows itself, so trimming it changes nothing but the file.
    program = "\n".join("".join(row).rstrip() for row in grid)
    if width is None:
        partially_stacked = clockwise(truth_table, width=8 * n)
        return min((program, partially_stacked), key=len)
    return program


def container(truth_table: str) -> str:
    """Build a Container program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Container is a synchronous rule system: every tick each container's value
    becomes ``max(old + sum of deltas of satisfied ``X>=Y``/``X<=Y`` rules,
    0)``, the empty-named container reads a line of input into ``IN`` when it
    turns on, ``PRINT`` outputs ``OUT`` when it turns on, and ``EXIT`` halts
    when its value changes.  There is no per-tick conditional, so the
    generator timestamps everything with the tick counter ``T``:

    * The empty container pulses on even ticks ``0..2(n-1)`` (``+1 T>=2k``,
      ``-2 T>=2k+1``, ``+1 T>=2k+2``), reading one bit per pulse.
    * For each bit ``k``, two armed gates (65, dipping to 49; and 47, dipping
      to 48) make their ``IN`` comparisons hold for
      exactly the tick the bit is in ``IN``, testing bit ``k`` once.
    * A prefix survivor creates its two children while bit ``k`` is active;
      the mismatching child is cancelled in that same tick.  The parent then
      expires, so each tree edge costs constant work instead of retesting the
      whole prefix at every leaf.
    * At tick ``2n`` an output gate dips to 1, so the surviving row adds the
      table entry of the surviving row to ``OUT``; ``PRINT`` fires and
      ``EXIT`` halts.

    The last block costs one line per row the table sends to 1, so a dense
    table is summed from its **zero** rows instead: ``OUT`` starts at 49 and
    each surviving zero row subtracts one, printing ``49 - S``.  The clamp at
    zero never bites, since the value stays at 48 or 49.  Worth up to 12.7%
    at ``n == 4`` (1356 characters down to 1184 for fifteen ones of sixteen);
    the per-row survivor blocks above are fixed and unaffected.
    """
    n = _validate_truth_table(truth_table)
    ones = truth_table.count("1")
    invert = ones > 2**n - ones
    wanted = "0" if invert else "1"

    # Every generated container has a unique name, but their reference counts
    # differ sharply.  Assign shortest alphabetic names by actual frequency.
    uses: dict[tuple[str, int, int], int] = {("root", 0, 0): 6}
    for bit in range(n):
        uses[("low", bit, 0)] = 1 + 2**bit
        uses[("high", bit, 0)] = 1 + 2**bit
    for depth in range(1, n + 1):
        for prefix in range(2**depth):
            uses[("node", depth, prefix)] = (
                6 if depth < n else 2 + (truth_table[prefix] == wanted)
            )
    uses[("output", 0, 0)] = 1 + truth_table.count(wanted)

    reserved = {"EXIT", "IN", "OUT", "PRINT", "T"}
    identifiers = (_forbin_name(i) for i in range(len(uses) + len(reserved)))
    ordered = sorted(uses, key=lambda key: (-uses[key], key))
    names: dict[tuple[str, int, int], str] = {}
    for key in ordered:
        name = next(identifiers)
        while name in reserved:
            name = next(identifiers)
        names[key] = name

    root = names[("root", 0, 0)]
    output_gate = names[("output", 0, 0)]

    lines = ["T:", "+1 T>=T"]
    lines.append(":")  # the empty-named container reads input
    lines.append("+1 T>=0")
    lines.append("-2 T>=1")
    for k in range(1, n):
        lines.append(f"+2 T>={2 * k}")
        lines.append(f"-2 T>={2 * k + 1}")
    lines.append(f"+1 T>={2 * n}")
    lines.append("IN=50:")  # a value no real byte matches
    for k in range(n):
        low = names[("low", k, 0)]
        high = names[("high", k, 0)]
        lines.append(f"{low}=65:")
        lines.append(f"-16 T>={2 * k}")
        lines.append(f"+32 T>={2 * k + 1}")
        lines.append(f"-16 T>={2 * k + 2}")
        lines.append(f"{high}=47:")
        lines.append(f"+1 T>={2 * k}")
        lines.append(f"-2 T>={2 * k + 1}")
        lines.append(f"+1 T>={2 * k + 2}")
    lines.append(f"{root}=2:")
    lines.append(f"-1 {root}>=1")
    for depth in range(1, n + 1):
        bit = depth - 1
        for prefix in range(2**depth):
            parent = root if depth == 1 else names[("node", depth - 1, prefix >> 1)]
            child = names[("node", depth, prefix)]
            lines.append(f"{child}:")
            # A node is born at 2, decays to 1, then pulses its children.
            # The paired parent rules therefore fire only at exactly 1.
            lines.append(f"+2 {parent}>=1")
            lines.append(f"-2 {parent}>=2")
            gate = names[("high" if prefix & 1 else "low", bit, 0)]
            mismatch = f"IN<={gate}" if prefix & 1 else f"IN>={gate}"
            lines.append(f"-2 {mismatch}")
            lines.append(f"-1 {child}>=1")
    lines.append(f"{output_gate}=2:")
    lines.append(f"-1 T>={2 * n - 1}")
    lines.append(f"+1 T>={2 * n}")
    # OUT is 48 plus one ``+1`` per row the table sends to 1, so a dense
    # table pays for nearly every row.  Evaluating the *zero* rows costs one
    # line each and starts from 49, subtracting: ``49 - S`` is the
    # complement, and since ``S`` is 0 or 1 the value stays at 48 or 49, so
    # the container's clamp at zero never bites.  Whichever row-set is
    # smaller wins; ties keep the plain form.
    lines.append("OUT:")
    lines.append(f"+{_ASCII_ZERO + 1 if invert else _ASCII_ZERO} T>={2 * n}")
    lines.append(f"-{_ASCII_ZERO + 1 if invert else _ASCII_ZERO} T>={2 * n + 1}")
    delta = "-1" if invert else "+1"
    for row in range(2**n):
        if truth_table[row] == wanted:
            lines.append(f"{delta} {names[('node', n, row)]}>={output_gate}")
    lines.append("PRINT:")
    lines.append(f"+1 T>={2 * n}")
    lines.append("EXIT=1:")
    lines.append(f"-1 T>={2 * n + 1}")
    return "\n".join(lines)


def bit_tilde(truth_table: str) -> str:
    """Build a bit~ program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    bit~ is a bit pool with ``{``/``}`` while-nonzero loops. Each node copies
    its stored input into two indicators, complements the zero indicator,
    then uses both as one-shot branch loops. The loop body clears its own
    indicator, so both paths converge and scratch cells can be reused by
    depth. Deep levels occupy cells nearest the input area; their repeated
    pointer walks therefore form a geometric sum and the source is O(T).
    """
    n = _validate_truth_table(truth_table)

    used = essential_inputs(truth_table, n) or [0]
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    width = len(used)

    prog: list[str] = []
    pos = 0

    def move(dst: int) -> None:
        nonlocal pos
        while pos < dst:
            prog.append(">")
            pos += 1
        while pos > dst:
            prog.append("<")
            pos -= 1

    def copy2(src: int, d1: int, d2: int) -> None:
        """Copy ``src`` to ``d1`` and ``d2``, zeroing ``src``."""
        nonlocal pos
        move(src)
        prog.append("{")
        move(d1)
        prog.append("~")
        move(d2)
        prog.append("~")
        move(src)
        prog.append("~")
        prog.append("}")

    for i in range(n):
        if i:
            move(8 * i)
        prog.append(")")
        pos = 8 * i

    base = 8 * n
    result = base

    def set_result() -> None:
        nonlocal pos
        move(result)
        prog.append("{ ~ } ~")
        pos = result

    def clear(cell: int) -> None:
        nonlocal pos
        move(cell)
        prog.append("{~}")
        pos = cell

    changes = [0]
    for previous, current in pairwise(table):
        changes.append(changes[-1] + (previous != current))

    def node(start: int, end: int, depth: int) -> None:
        nonlocal pos
        if changes[start] == changes[end - 1]:
            if table[start] == "1":
                set_result()
            return
        half = (start + end) // 2
        slot = width - 1 - depth
        zero = base + 1 + 3 * slot
        one = zero + 1
        temp = zero + 2
        for cell in (zero, one, temp):
            clear(cell)
        source = 8 * used[depth] + 7
        copy2(source, one, temp)
        copy2(temp, source, zero)
        move(zero)
        prog.append("~{")
        pos = zero
        node(start, half, depth + 1)
        move(zero)
        prog.append("~}")
        pos = zero
        move(one)
        prog.append("{")
        pos = one
        node(half, end, depth + 1)
        move(one)
        prog.append("~}")
        pos = one

    node(0, 1 << width, 0)

    # Cell 7 still holds input 0 because tree copies preserve every source.
    clear(7)
    move(result)
    prog.append("{")
    move(7)
    prog.append("~")
    move(result)
    prog.append("~")
    prog.append("}")
    pos = result
    move(0)
    prog.append("(")
    return "".join(prog)


def forbin(truth_table: str) -> str:
    """Build a Forbin program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Forbin's ``in`` reads one bit (most significant first), so each input
    byte contributes 8 reads and only the last bit (the LSB, which is what
    distinguishes ``'0'`` from ``'1'``) is used.  A decision tree over those
    bits is laid out with the range-loop if-trick: ``for _:!b..b`` runs its
    body once when ``b`` is 1 (the ``return`` cuts the second iteration)
    and falls through when ``b`` is 0, so each node emits the 1-subtree then
    the 0-subtree and every leaf prints the result byte and returns.

    **The tree splits on its inputs in whichever order emits the shortest
    program** (:func:`~esolangs.tools.helpers.best_input_order`).
    The ``(in 0)`` reads stay in input order -- all ``8n`` of them -- so
    only the bit a ``for`` names moves.
    """
    return best_input_order(truth_table, _forbin_ordered)


_FORBIN_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_FORBIN_RESERVED = {"for", "in", "main", "out", "return"}


def _forbin_name(index: int) -> str:
    """Return the ``index``th shortest non-keyword identifier."""
    base = len(_FORBIN_ALPHABET)
    candidate = 0
    while True:
        value = candidate + 1
        chars = []
        while value:
            value, digit = divmod(value - 1, base)
            chars.append(_FORBIN_ALPHABET[digit])
        name = "".join(reversed(chars))
        if name not in _FORBIN_RESERVED:
            if index == 0:
                return name
            index -= 1
        candidate += 1


def _forbin_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's Forbin program; see :func:`forbin`."""
    n = _validate_truth_table(truth_table)

    lines: list[str] = ["main {"]
    bits = [""] * n
    depth_of = {stream: depth for depth, stream in enumerate(perm)}
    for i in range(n):
        depth = depth_of[i]
        # Deep levels are repeated exponentially more often in the emitted
        # tree, so allocate their eight input bits first.
        start = 8 * (n - 1 - depth)
        reads = [_forbin_name(start + j) for j in range(8)]
        lines.append(f"  {','.join(reads)} = (in 0);")
        bits[depth] = reads[7]

    # ``changes[i]`` counts value boundaries through entry ``i``.  An
    # interval is constant iff its endpoints see the same count, so every
    # node's fold test is O(1) after this one linear pass.
    changes = [0]
    for previous, current in pairwise(truth_table):
        changes.append(changes[-1] + (previous != current))

    def emit(level: int, row: int) -> None:
        end = row + 2 ** (n - level)
        if level == n or changes[row] == changes[end - 1]:
            byte = _ASCII_ZERO + int(truth_table[row])
            lines.append(f"  out {','.join(format(byte, '08b'))};")
            lines.append("  return 0;")
            return
        bit = bits[level]
        lines.append(f"  for _:!{bit}..{bit} {{")
        emit(level + 1, row + 2 ** (n - 1 - level))
        lines.append("  }")
        emit(level + 1, row)

    emit(0, 0)
    lines.append("}")
    return "\n".join(lines)


# A leaf is exactly as wide as the ``(( ))`` it ends on, so consecutive
# leaves abut and the tree needs no gutter between them at all.
_FLOWCHART_PITCH = 5


def _flowchart_cells(truth_table: str) -> dict[tuple[int, int], str]:
    """Paint the decision tree onto a sparse ``(x, y) -> character`` grid.

    Leaves are placed first, on a fixed pitch, and the switches are then
    collapsed upwards: each pair of entry columns yields a ``< >`` centred
    between them with rails drawn out to both.  Positioning everything from
    the leaf pitch keeps the drawing tight -- an earlier recursive version
    assembled each subtree into its own padded block and separated the blocks
    by a gutter, costing a column of blanks for every leaf at every level
    even though two ``(( ))`` boxes may sit flush against each other.

    Rows run ``( )``, its rail, then four rows per level (``/ /``, a rail,
    ``< >``, a rail), then the five-row leaf block.
    """
    cells: dict[tuple[int, int], str] = {}
    constant = constant_span_test(truth_table)

    def put(x: int, y: int, text: str) -> None:
        for i, char in enumerate(text):
            cells[(x + i, y)] = char

    n = (len(truth_table) - 1).bit_length()
    leaf_top = 2 + 4 * n

    def leaf(slot: int, bit: str) -> int:
        """Draw the leaf for ``bit`` in column slot ``slot``; return its middle.

        Leaf ``k`` spans columns ``5k`` to ``5k + 4``, so its middle -- the
        column every rail in that leaf's band lands on -- is ``5k + 2``.
        """
        middle = _FLOWCHART_PITCH * slot + 2
        put(middle - 1, leaf_top, "[ }" if bit == "1" else "{ ]")
        cells[(middle, leaf_top + 1)] = "│"
        put(middle - 1, leaf_top + 2, "\\ \\")
        cells[(middle, leaf_top + 3)] = "│"
        put(middle - 2, leaf_top + 4, "(( ))")
        return middle

    def switch(depth: int, west: int, east: int) -> int:
        """Join two subtrees at ``depth``; return the column it sits on."""
        switch_row = 4 + 4 * depth
        middle = (west + east) // 2
        put(middle - 1, switch_row - 2, "/ /")
        cells[(middle, switch_row - 1)] = "│"
        put(middle - 1, switch_row, "< >")
        for x in range(west + 1, middle - 1):
            cells[(x, switch_row)] = "─"
        for x in range(middle + 2, east):
            cells[(x, switch_row)] = "─"
        cells[(west, switch_row)] = "┌"
        cells[(east, switch_row)] = "┐"
        cells[(west, switch_row + 1)] = "│"
        cells[(east, switch_row + 1)] = "│"
        return middle

    # Slots are handed out left to right as the walk reaches each leaf, so a
    # folded subtree takes one column band instead of the ``2**k`` its rows
    # would have filled -- the drawing narrows rather than leaving a gap.
    slots = [0]

    def walk(lo: int, hi: int, depth: int) -> int:
        """Draw the subtree for ``truth_table[lo:hi]``; return its column.

        ``depth`` is the level it sits at, which fixes its rows; its columns
        come from the leaf slots it consumes.
        """
        if constant(lo, hi):
            # Constant: no branch below here can change the answer, so this
            # is a leaf.  Leaves all sit on the bottom row whatever their
            # depth, so the rail from the switch above covers the levels this
            # fold skipped: the rows are a fixed grid and only the branching
            # goes away.
            #
            # The *reads* those levels would have done do not go away.  A
            # program must consume its ``n`` inputs whatever the table says
            # -- the reads are the interface, and a folded run that skipped
            # them left the caller's remaining bits on the stream -- so each
            # skipped level puts its ``/ /`` on the rail, where the pointer
            # runs straight through it into the leaf below.
            middle = leaf(slots[0], truth_table[lo])
            slots[0] += 1
            for y in range(4 * depth + 2, leaf_top):
                cells.setdefault((middle, y), "│")
            for skipped in range(depth, n):
                put(middle - 1, 4 * skipped + 2, "/ /")
            return middle
        half = (hi - lo) // 2
        west = walk(lo, lo + half, depth + 1)
        east = walk(lo + half, hi, depth + 1)
        return switch(depth, west, east)

    root = walk(0, len(truth_table), 0)
    put(root - 1, 0, "( )")
    cells[(root, 1)] = "│"
    return cells


def _flowchart_render(cells: dict[tuple[int, int], str]) -> str:
    """Flatten a painted cell map into the finished program text."""
    height = max(y for _, y in cells) + 1
    width = max(x for x, _ in cells) + 1
    grid = [[" "] * width for _ in range(height)]
    for (x, y), char in cells.items():
        grid[y][x] = char
    return "\n".join("".join(row).rstrip() for row in grid)


def _flowchart_stacked(truth_table: str) -> dict[tuple[int, int], str]:
    """Paint the tree with its subtrees stacked rather than side by side.

    The flat drawing gives every leaf a column of its own, so it grows as
    ``2 ** n``.  Stacking separates the two subtrees by *rows* instead: the
    one-branch hangs directly below the switch, and the zero-branch falls
    down a column of its own, past every row the one-branch occupies, to
    start below it.  Every node then sits on the same column, and what the
    width costs is height -- the drawing is as tall as the whole tree.

    A switch entered travelling down sends register 1 to the grid-east and
    register 0 to the grid-west, so neither branch may simply continue
    down; each is caught by a corner and routed.  The one-branch turns down
    one column east, comes back west a row later, and drops onto the spine.
    The zero-branch runs west to a column reserved for its depth, falls the
    height of the one-branch, and comes back east.

    Those corridors need no crossings, which is what keeps the drawing
    simple.  A corridor for depth ``d`` occupies column ``d``, and
    everything below it in the tree is at a *deeper* depth and so further
    east; the rails that run west to reach it do so on the switch's own
    row, above every descendant.  So no rail and no corridor ever meet.
    """
    n = (len(truth_table) - 1).bit_length()
    # Columns 0..n-1 are the corridors, one per depth; the tree itself sits
    # on ``spine``, far enough east that a leaf's five-cell ``(( ))`` clears
    # them.
    spine = n + 2
    cells: dict[tuple[int, int], str] = {}
    constant = constant_span_test(truth_table)

    def put(x: int, y: int, text: str) -> None:
        for i, char in enumerate(text):
            cells[(x + i, y)] = char

    def reads(y: int, count: int) -> int:
        """Draw ``count`` ``/ /`` nodes down the spine; return the row after."""
        for _ in range(count):
            put(spine - 1, y, "/ /")
            cells[(spine, y + 1)] = "│"
            y += 2
        return y

    def leaf(y: int, depth: int, bit: str) -> int:
        """Draw the leaf for ``bit``, entered at ``(spine, y)``.

        A folded leaf still owes the reads of the levels it skipped -- the
        reads are the interface -- and here they simply stack above it,
        which is what the flat drawing spends a rail on.
        """
        y = reads(y, n - depth)
        put(spine - 1, y, "[ }" if bit == "1" else "{ ]")
        cells[(spine, y + 1)] = "│"
        put(spine - 1, y + 2, "\\ \\")
        cells[(spine, y + 3)] = "│"
        put(spine - 2, y + 4, "(( ))")
        return y + 5

    def walk(lo: int, hi: int, depth: int, y: int) -> int:
        """Draw the subtree for ``truth_table[lo:hi]``; return the row after."""
        if constant(lo, hi):
            return leaf(y, depth, truth_table[lo])
        put(spine - 1, y, "/ /")
        cells[(spine, y + 1)] = "│"
        put(spine - 1, y + 2, "< >")
        # b=1: east out of the switch, down, back west, onto the spine
        cells[(spine + 2, y + 2)] = "┐"
        cells[(spine + 2, y + 3)] = "┘"
        cells[(spine + 1, y + 3)] = "─"
        cells[(spine, y + 3)] = "┌"
        half = (hi - lo) // 2
        below = walk(lo + half, hi, depth + 1, y + 4)
        # b=0: west to this depth's own column, down past everything the
        # one-branch drew, then east again onto the spine
        for x in range(depth + 1, spine - 1):
            cells[(x, y + 2)] = "─"
        cells[(depth, y + 2)] = "┌"
        for row in range(y + 3, below):
            cells[(depth, row)] = "│"
        cells[(depth, below)] = "└"
        for x in range(depth + 1, spine):
            cells[(x, below)] = "─"
        cells[(spine, below)] = "┐"
        return walk(lo, lo + half, depth + 1, below + 1)

    walk(0, len(truth_table), 0, 2)
    put(spine - 1, 0, "( )")
    cells[(spine, 1)] = "│"
    return cells


def flowchart(truth_table: str, width: int | None = None) -> str:
    """Build a Flowchart program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The program is a binary decision tree drawn on the grid: every level
    reads one input bit with ``/ /`` and hands it to a ``< >`` switch whose
    two sides are the halves of the table, and each of the ``2**n`` leaves
    sets the register to its own digit, prints it, and halts.

    Unlike the repo's other 2D boolean generators there is no geometry to
    build for the branch itself -- Flowchart has a real conditional node --
    and each input arrives as a bare bit, so no per-input decoding loop is
    needed either.  What the layout has to get right instead is routing:
    every switch is centred over the two subtree entries it feeds, with
    rails drawn out to each.

    The leaves are laid down first, on a pitch of exactly one ``(( ))``
    width, and the switches are collapsed upwards from them.  Nothing
    separates one leaf from the next: two ``(( ))`` boxes may sit flush
    against each other, since a rail only has to clear a node when it needs
    to pass *through* that node's row.  Sibling subtrees never do -- they
    descend in their own column bands -- so the gutter an earlier version
    kept between them was never required, and dropping it takes the
    ``n = 4`` drawing from 2444 characters to 1557.

    **The tree holds many ``/ /`` nodes but reads each input once.**  A
    depth-``n`` tree draws ``2**n - 1`` read nodes, one per internal node,
    yet any single run walks one root-to-leaf path and so executes exactly
    ``n`` of them -- which is why a *folded* leaf carries the reads of the
    levels it skipped on its own rail.  Without them a run that folded early
    would consume fewer inputs than one that did not, making the program's
    stream consumption a function of its truth table; only the branching may
    fold away, never the reads.  The duplication is spatial, the way an
    unrolled brainfuck branch repeats ``,`` in each arm of a nested ``[ ]``
    without any one execution reading twice.  This is deliberately *not* the
    once-only embedding rule that ``tools.parameterized`` documents:
    that rule exists so a language with no input mechanism cannot, through
    repeated ``{Xi}`` substitution, consult a bit more often than an
    input-capable language would.  Flowchart has a real input command, so it
    is an input-reading generator like :func:`streetcode` (whose ``I``
    commands likewise repeat across tree branches), not a parameterized one.

    An alternative construction reads all ``n`` bits up front into a deque
    and pops one per level instead, exercising the deques -- the language's
    defining feature, untouched here.  It was built and verified over the
    same tables, and is worth revisiting if Flowchart ever gets a cross-check
    that would benefit from the wider coverage; it costs a ``4n``-row
    prologue and depends on push-top/pop-bottom being FIFO, a silent
    wrong-answer trap if the pop is ever changed to pop-top.
    Without a width, both named layouts are built and the shorter rendered
    program wins; this is a fixed two-way comparison, not a layout search.
    ``width`` asks for a column count.  The flat drawing gives every leaf a
    column of its own and so grows as ``2 ** n``; a width under that is met
    by *stacking* the tree instead, separating the two subtrees by rows and
    putting every node on one column.  See :func:`_flowchart_stacked` for
    how the branches are routed and why the corridors never cross.  The
    stacked drawing is ``n + 5`` columns whatever the table, so the width
    stops tracking ``n`` -- and pays for it in height, being as tall as the
    whole tree.  A width under that floor returns the narrower of the two
    rather than refusing, and a heavily folded table is sometimes already
    narrower flat.
    """
    _validate_truth_table(truth_table)
    flat = _flowchart_render(_flowchart_cells(truth_table))
    if width is not None and max(len(line) for line in flat.split("\n")) <= width:
        return flat
    stacked = _flowchart_render(_flowchart_stacked(truth_table))
    if width is None:
        return min((flat, stacked), key=len)
    if max(len(line) for line in stacked.split("\n")) < max(
        len(line) for line in flat.split("\n")
    ):
        return stacked
    return flat
