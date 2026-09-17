"""Boolean-function generator for WII2D (parameterized convention).

The template's input runs are junction cells the harness fills with ``>``
(bit 0) or ``v`` (bit 1).  The branch op strings are constructed, not
searched: :func:`_wii2d_chain` takes the first legal junction pair per
input (Horner is always legal) and :func:`_wii2d_decode` takes the single
best fold per step, so the program is a direct function of the table.
"""

import heapq

from esolangs.exceptions import GeneratorCapError
from esolangs.tools.helpers import _ASCII_ZERO, TEMPLATE_CHAR, _validate_truth_table

__all__ = ["wii2d"]

#: ``>`` continues east for a zero, ``v`` takes the 1-branch below.  One
#: grid cell, so a run is the exact width of its program.
WII2D_ZERO, WII2D_ONE = ">", "v"
_WII2D_INPUT = TEMPLATE_CHAR * len(WII2D_ZERO)


# Ops: digits set the accumulator; ``+ - * / s`` increment, decrement,
# double, halve, square; space is a no-op.  Only ``s`` is not
# order-preserving, so the decode is folds around it.

# The fold rule is deterministic: :func:`_wii2d_decode` takes the single best
# candidate from :func:`_wii2d_folds` (smallest magnitude, fewest live
# values, shortest op string).  No beam, no width ladder, no retry.
# The fold reshapes; :func:`_wii2d_compress` merges, by steering an
# add-then-halve run's shift onto collisions.  Dense ``D == 256`` decodes 18
# of 20 sampled patterns vs 3 of 10 for the one-level halving it replaced.
# Exhaustive over every 0/1 pattern through ``D == 16`` (the widest general
# domain), verified by applying the op string back over the domain.

# A centre is spelled ``'-' * c``, so this bounds program width, not the
# arithmetic.  Compression keeps centres tiny (medians < 100 columns); this
# rejects drifted outliers and every pattern through ``D == 16`` still decodes.
_WII2D_MAX_CENTRE = 4096

# Divergence certificate, not a step budget.  Successful decodes stay small
# (max 1922 over the 532-table corpus, 13499 over eight domain-256 samples);
# a failing one ratchets, ~doubling bit length per step (a domain-512 run:
# 14 -> 670597 bits).  2**20 is 78x the largest success.
# Load-bearing: with it lifted, three domain-256 tables that abort in
# 0.45-1.59s ran 136s / 183s / 214s and were still climbing (299526,
# 1173459, 644663 bits).  Checked on the state, not the candidates, so it
# cannot change a succeeding table's choice; deterministic where a clock is not.
_WII2D_MAX_MAGNITUDE = 1 << 20

# Candidates compressed before the true ranking.  Compression is the
# expensive half and the decode takes only the head.  A screen, not a bound:
# compression is a contraction, so the uncompressed magnitude barely predicts
# the compressed one.  Raised 4 -> 8 with steered compression: at 4 the
# corpus emitted 286669 chars (vs 285903 one-level); at 8, 261019 (-8.7%).
_WII2D_SHORTLIST = 8

# Legal shifts scored per depth.  The legal set is exact; this takes the
# first few of each gap, so the smallest is always included.  Same status
# as the shortlist.
_WII2D_SHIFT_SAMPLES = 40

# Widest general (non-symmetric) decode domain, so that path runs to n == 9.
# A cost policy, charged against :func:`_wii2d_cost` -- min of ``2 ** (n - 1)``
# and the domain the chain actually leaves -- so an n == 8 xor-of-a-subset
# collapses to 4 points and builds in 217 chars.  Symmetric tables never
# reach this (popcount chain over n points).
# Dense n == 9 usually builds: the sha256 witness table takes 1.1s, 78362
# chars, all 512 rows executed.  Every sampled failure returns promptly
# (:data:`_WII2D_MAX_MAGNITUDE` guarantees it), which made 128 -> 256 safe.
# Dense n == 10 (512) is refused by the fold algebra, not the number: at 512
# the witness ratchets, live count 512 -> 475 over 19 steps while bits go
# 9 -> 1089888 (step 19 alone 144s); full enumeration 512 -> 373, > 670000 bits.
_WII2D_MAX_INDEX_DOMAIN = 256

# Widest *real* chain domain.  The guard above charges the minimum, so a
# table admitted on its worst case can have its real domain run away when no
# merge is legal and the walk falls through to Horner.  Rare but unbounded;
# 256 is above every overshoot that decodes and below the one that does not.
_WII2D_MAX_REAL_DOMAIN = 256


def _wii2d_apply(ops: str, value: int) -> int:
    """Apply a WII2D op string to an accumulator value (the op cell order)."""
    for op in ops:
        if op == "+":
            value += 1
        elif op == "-":
            value -= 1
        elif op == "*":
            value *= 2
        elif op == "/":
            value //= 2
        elif op == "s":
            value *= value
        elif op != " ":
            value = int(op)
    return value


def _wii2d_offset(c: int) -> str:
    """Return the op string subtracting ``c`` (``'-'`` or ``'+'`` repeated)."""
    return "-" * c if c >= 0 else "+" * (-c)


def _wii2d_points(values: list[int], bits: list[int]) -> dict[int, int] | None:
    """Map each live accumulator value to its required bit.

    ``None`` when two inputs share a value but need different bits: unrecoverable.
    """
    seen: dict[int, int] = {}
    for value, bit in zip(values, bits, strict=True):
        if seen.get(value, bit) != bit:
            return None
        seen[value] = bit
    return seen


def _wii2d_legal_shifts(arcs: list[tuple[int, int]], block: int) -> list[int]:
    """Return up to :data:`_WII2D_SHIFT_SAMPLES` legal shifts, ascending.

    ``arcs`` are bad cyclic intervals ``(start, length)`` modulo ``block``;
    the gaps between them are walked in order, so the smallest legal shift leads.
    """
    if not arcs:
        return list(range(min(_WII2D_SHIFT_SAMPLES, block)))
    flat = []
    for start, length in arcs:
        end = start + length
        if end <= block:
            flat.append((start, end))
        else:  # wraps: split at the block boundary
            flat.append((start, block))
            flat.append((0, end - block))
    flat.sort()
    out: list[int] = []
    covered = 0
    for start, end in flat:
        for shift in range(covered, min(start, covered + 4)):
            out.append(shift)
            if len(out) >= _WII2D_SHIFT_SAMPLES:
                return out
        covered = max(covered, end)
        if covered >= block:
            return out
    for shift in range(covered, min(block, covered + 4)):
        out.append(shift)
        if len(out) >= _WII2D_SHIFT_SAMPLES:
            break
    return out


def _wii2d_compress(
    values: list[int], bits: list[int], ops: str
) -> tuple[list[int], str]:
    """Merge and shrink the live values with add-then-halve runs.

    ``k`` halvings with an optional ``+`` before each is ``v -> (v + S) //
    2**k``, so the family is searched directly.  Two values share a block iff
    ``S`` falls in a cyclic arc; each different-bit pair at gap ``g < 2**k``
    forbids ``2**k - g`` shifts, and legality is monotone in ``k``, so the
    depth scan stops at the first empty level.  Rule: the ``(k, S)`` merging
    the most values, deepest then smallest shift; repeat until none is legal.
    Steering ``S`` onto collisions is the engine's merging half and what
    carries dense domains past the squaring blow-up.  Each run strictly
    shrinks the span, so this terminates.
    """
    while True:
        live = _wii2d_points(values, bits)
        if live is None:  # pragma: no cover - callers pass legal states
            return values, ops
        points = sorted(live)
        span = points[-1] - points[0]
        # Stop on magnitude, not span: a small span at a large magnitude
        # still shrinks, and span alone hands the threshold huge offsets.
        if max(abs(p) for p in (points[0], points[-1])) <= 1:
            return values, ops
        best: tuple[tuple[int, int, int], int, int] | None = None
        depth = 1
        while (1 << depth) <= 2 * span + 2:
            block = 1 << depth
            arcs = []
            for i, low in enumerate(points):
                for high in points[i + 1 :]:
                    gap = high - low
                    if gap >= block:
                        break
                    if live[low] != live[high]:
                        arcs.append(((-low) % block, block - gap))
            shifts = _wii2d_legal_shifts(arcs, block)
            if not shifts:
                break
            for shift in shifts:
                blocks = {(p + shift) >> depth for p in points}
                key = (len(points) - len(blocks), depth, -shift)
                if best is None or key > best[0]:
                    best = (key, depth, shift)
            depth += 1
        if best is None:
            return values, ops
        _key, depth, shift = best
        ops += "".join("+" * ((shift >> k) & 1) + "/" for k in range(depth))
        values = [(v + shift) >> depth for v in values]


def _wii2d_threshold(live: dict[int, int]) -> str:
    """Return the op string collapsing one or two live values to their bits.

    One value: a digit.  Two: ``x -> (x - t) // 2 ** k`` drives the lower to
    -1 and the upper to 0, and ``+`` reads out ``[x >= t]``; ``-s`` flips it.
    """
    points = sorted(live)
    if len(points) == 1:
        return str(live[points[0]])
    low, high = points
    if live[low] == live[high]:
        # One label for both values: a digit resets both (the indicator
        # below can only answer (0, 1) or (1, 0)).
        return str(live[low])
    # After subtraction the values are ``low - high`` and 0; halve until -1.
    runs = max(abs(low - high).bit_length() + 1, 1)
    indicator = _wii2d_offset(high) + "/" * runs + "+"
    if live[low] == 0 and live[high] == 1:
        return indicator
    return indicator + "-s"


def _wii2d_folds(
    values: list[int], bits: list[int]
) -> list[tuple[int, int, int, str, list[int]]]:
    """Return the candidate folds from this state, best first.

    ``'-' * c + 's'`` sends ``x`` to ``(x - c) ** 2``, merging exactly the
    pairs equidistant from ``c`` -- the one way to make two values agree
    without a conditional.  Legal only when every merged pair needs the same
    bit; doubling first opens half-integral midpoints.  Only the first
    :data:`_WII2D_SHORTLIST` are compressed, ranked uncompressed (a screen,
    not a bound), which keeps the per-step cost flat.
    """
    # Legal folds by pair, uncompressed.  ``(p - c) ** 2`` collides exactly
    # for pairs symmetric about ``c``: a centre is illegal iff some pair
    # summing to ``2c`` differs in bit, and merges = live - same-bit pairs at
    # ``2c`` (disjoint, since at most two points share one ``abs(p - c)``).
    # O(P**2) instead of the per-centre rescan's O(P**3): 5.6s of the 6.3s
    # dense n == 9 build was that loop.  Same candidate set.
    # Only the shortlist is compressed; the caller takes the head.
    pending: list[tuple[tuple[int, int, int], int, int, int]] = []
    for scale in (0, 1):
        scaled = [v * 2 for v in values] if scale else list(values)
        live = _wii2d_points(scaled, bits)
        if live is None:
            continue
        points = sorted(live)
        span_low, span_high = points[0], points[-1]
        zeros = [p for p in points if live[p] == 0]
        ones = [p for p in points if live[p] == 1]
        # ``2c`` for every pair that would fold two different bits together
        crossing: set[int] = set()
        for point in zeros:
            crossing.update([point + other for other in ones])
        # ``2c -> how many same-bit pairs that centre merges``
        merging: dict[int, int] = {}
        for group in (zeros, ones):
            for index, point in enumerate(group):
                for double in [point + other for other in group[index + 1 :]]:
                    merging[double] = merging.get(double, 0) + 1
        # Sorted: ranking ties break on append order, and hash order would
        # make the program depend on the machine.
        for double in sorted(merging):
            if double % 2 or double in crossing:
                continue
            centre = double >> 1
            if abs(centre) > _WII2D_MAX_CENTRE:
                continue  # correct but too wide to spell out in the grid
            # Shortlist key on the uncompressed state -- a screen, not the
            # ranking (compression can take 529 to 17).  Squares are monotone
            # in distance from the centre, so the widest value is a span end.
            pending.append(
                (
                    (
                        max((span_low - centre) ** 2, (span_high - centre) ** 2),
                        len(points) - merging[double],
                        scale + abs(centre) + 1,
                    ),
                    len(pending),  # stable-sort tie-break, made explicit
                    scale,
                    centre,
                )
            )

    # Compress only the shortlist, then rank those on their true keys.
    out: list[tuple[int, int, int, str, list[int]]] = []
    for _screen, _index, scale, centre in heapq.nsmallest(_WII2D_SHORTLIST, pending):
        scaled = [v * 2 for v in values] if scale else values
        fragment = ("*" if scale else "") + _wii2d_offset(centre) + "s"
        folded_values = [(v - centre) ** 2 for v in scaled]
        compressed, grown = _wii2d_compress(folded_values, bits, fragment)
        out.append(
            (
                len(set(compressed)),
                max(abs(v) for v in compressed),
                len(grown),
                grown,
                compressed,
            )
        )
    # Magnitude first: centres are spelled ``'-' * c``, so live values are
    # program width.  Survivors first: 396131 chars vs 285903 over the
    # 532-table corpus (+39%), under both compressions.
    out.sort(key=lambda cand: (cand[1], cand[0], cand[2]))
    return out


def _wii2d_decode(pattern: list[int]) -> str | None:
    """Construct an op string realizing ``pattern`` on ``0 .. len(pattern)-1``.

    Repeatedly takes the single best fold from :func:`_wii2d_folds` until two
    values remain, then :func:`_wii2d_threshold`.  Each fold merges a pair,
    so at most ``len(pattern)`` steps.  ``None`` only if some step offers no
    legal fold, which no pattern through ``D == 16`` does.
    """
    bits = list(pattern)
    if all(bit == bits[0] for bit in bits):
        return str(bits[0])  # constant: a digit is the whole decode
    values, ops = _wii2d_compress(list(range(len(bits))), bits, "")
    # A fold strictly reduces the live count; the bound is a guard, not a budget.
    for _ in range(len(bits) + 1):
        live = _wii2d_points(values, bits)
        if live is None:
            return None
        # Ratchet abort (see :data:`_WII2D_MAX_MAGNITUDE`).  Before the
        # two-live exit so the threshold's ``'-' * c`` is bounded too.
        if max(abs(v) for v in values) > _WII2D_MAX_MAGNITUDE:
            return None
        if len(live) <= 2:
            return ops + _wii2d_threshold(live)
        candidates = _wii2d_folds(values, bits)
        if not candidates:
            return None
        # Best-first; the head is the whole choice.
        *_rank, fragment, folded = candidates[0]
        values, ops = folded, ops + fragment
    return None


# Junction pairs ``(A, B)``: ``A`` on input 0, ``B`` on input 1, shared by
# every path reaching the junction.  Tried in order, first legal wins -- one
# pass, no backtracking.  Earlier entries merge (same residual function ->
# same value, narrowing the decode); Horner ``('*', '*+')`` is last and
# always legal: children ``2v`` and ``2w + 1`` differ in parity and
# ``2v == 2w`` forces ``v == w``, which the distinct-cofactor invariant forbids.
#
# The order is tuned, not derived, and no sort key reproduces it: 1.9M
# candidates over 63 features, none monotone (control recovers 172 keys for
# a sorted list); indices 10 -> 11 and 17 -> 18 both descend in length.
# Permuting the merge entries changes 360 of 392 programs with zero errors;
# the shipped order beats 7 of 8 random permutations (57708 vs up to 59557).
_WII2D_JUNCTIONS: tuple[tuple[str, str], ...] = (
    ("", ""),
    ("", "+"),
    ("+", ""),
    ("", "-"),
    ("-", ""),
    ("", "-s"),
    ("-s", ""),
    ("0", "1"),
    ("1", "0"),
    ("0", "0"),
    ("1", "1"),
    ("", "0"),
    ("0", ""),
    ("", "1"),
    ("1", ""),
    ("/", "/"),
    ("/", "/+"),
    ("/+", "/"),
    ("", "/"),
    ("/", ""),
    ("*", "*+"),
)


def _wii2d_advance(
    states: list[tuple[str, int]], ops: tuple[str, str]
) -> list[tuple[str, int]] | None:
    """Read one input bit with ``ops``, or ``None`` if that pair is illegal.

    A state is ``(cofactor, value)``.  Illegal when two *different* cofactors
    land on one value (the accumulator is the only state); the same cofactor
    on one value is the merge that makes this narrower than Horner.
    """
    low, high = ops
    out: list[tuple[str, int]] = []
    for cofactor, value in states:
        half = len(cofactor) // 2
        out.append((cofactor[:half], _wii2d_apply(low, value)))
        out.append((cofactor[half:], _wii2d_apply(high, value)))
    out = list(dict.fromkeys(out))  # identical (cofactor, value) is one state
    seen: dict[int, str] = {}
    for cofactor, value in out:
        if value < 0:
            # The decode indexes by value, so a negative has no slot; keeps
            # values in ``0 .. 2 ** n`` and :func:`_wii2d_columns` total.
            return None
        if seen.setdefault(value, cofactor) != cofactor:
            return None
    return out


def _wii2d_chain(
    n: int, table: str
) -> tuple[list[tuple[str, str]], list[tuple[str, int]]]:
    """Build the first ``n - 1`` junctions and the states they leave.

    First legal pair from :data:`_WII2D_JUNCTIONS` per level; Horner is
    always legal, so this cannot fail.
    """
    states = [(table, 0)]
    routes: list[tuple[str, str]] = []
    for _ in range(n - 1):
        for ops in _WII2D_JUNCTIONS:
            advanced = _wii2d_advance(states, ops)
            if advanced is not None:
                routes.append(ops)
                states = advanced
                break
        else:  # pragma: no cover - Horner is legal at every level
            raise AssertionError("no legal junction pair; Horner should be total")
    return routes, states


def _wii2d_columns(states: list[tuple[str, int]]) -> tuple[list[int], list[int]]:
    """Return the last junction's two columns as patterns over the values.

    Each surviving cofactor is two entries wide; the patterns are indexed by
    value, dense from zero only under Horner, so the caller decodes ``0 .. max``.
    """
    width = max(value for _, value in states) + 1
    # Values are non-negative (:func:`_wii2d_advance`), so every state has a
    # slot.  Unreached slots are don't-cares left at zero.
    low = [0] * width
    high = [0] * width
    for cofactor, value in states:
        low[value] = int(cofactor[0])
        high[value] = int(cofactor[1])
    return low, high


def _wii2d_real_domain(states: list[tuple[str, int]]) -> int:
    """Return the decode domain the chain walk actually left.

    One past the largest surviving value, not the live count.
    """
    return max(value for _cofactor, value in states) + 1


def _wii2d_cost(n: int, states: list[tuple[str, int]]) -> int:
    """Return the decode width :data:`_WII2D_MAX_INDEX_DOMAIN` is charged.

    The smaller of ``2 ** (n - 1)`` and the real domain.  Merging collapses
    structured tables far below the worst case (at ``n == 7``, worst 64: a
    function of three inputs leaves 3-4, xor-of-a-subset 4-5, a weighted
    threshold 7-12, a mux 24-32, building in 186-339 chars, all 128 rows
    run).  A non-merging walk can also overshoot (0.5% at ``n == 5``, domain
    37 vs 16; 0.2% at ``n == 6``, 197 vs 32) and every overshoot decoded, so
    the minimum keeps the old contract and adds the narrow tables.
    """
    worst_case: int = 2 ** (n - 1)
    return min(worst_case, _wii2d_real_domain(states))


def _wii2d_routes(n: int, table: str) -> tuple[int, list[tuple[str, str]]] | None:
    """Construct the per-junction branch op strings realizing ``table``.

    ``acc = R[n-1][b_n-1](... R[0][b_0](start))``, no ``R[i][b]`` depending
    on earlier bits, so: junctions ``0 .. n-2`` from :func:`_wii2d_chain`
    (the accumulator names the residual function, sharing a value where two
    prefixes agree; Horner's ``('*', '*+')`` with no merges gives the plain
    index ``q``), then the last junction's two branches decode the surviving
    values via :func:`_wii2d_decode`, over a domain never wider than
    ``2 ** (n - 1)``.  A symmetric table short-circuits to ``('', '+')``
    junctions (popcount) and decodes over ``n`` points, which keeps
    majority-of-n reachable at any arity.  ``n == 2`` and parity have exact
    closed forms (:func:`_wii2d_n2_closed_form`, :func:`_wii2d_parity_routes`).
    """
    if n == 2:
        return 0, _wii2d_n2_closed_form(table)
    popcount_map = _wii2d_symmetric_popcount_map(n, table)
    if popcount_map is not None:
        parity_result = _wii2d_parity_routes(n, popcount_map)
        if parity_result is not None:
            return parity_result
        # Branch b sees popcount p of the first n - 1 bits; total is p + b.
        low = _wii2d_decode(popcount_map[:n])
        high = _wii2d_decode(popcount_map[1:])
        if low is not None and high is not None:
            return 0, [("", "+")] * (n - 1) + [(low, high)]
    # Walk before the cost guard: the walk is microseconds, and the guard
    # charges the domain it actually leaves (:func:`_wii2d_cost`).
    chain, states = _wii2d_chain(n, table)
    # Refused on cost, not capability; see the constants.
    if _wii2d_cost(n, states) > _WII2D_MAX_INDEX_DOMAIN:
        return None
    if _wii2d_real_domain(states) > _WII2D_MAX_REAL_DOMAIN:
        return None
    zero_column, one_column = _wii2d_columns(states)
    branch0 = _wii2d_decode(zero_column)
    branch1 = _wii2d_decode(one_column)
    if branch0 is None or branch1 is None:
        return None
    return 0, [*chain, (branch0, branch1)]


# n == 2 closed form: ``R0 = (-, *)`` packs bit 0 as -1 / 0, and each branch
# of the last junction decodes one column with a single op: 00 -> ``0``,
# 01 -> ``+``, 10 -> ``s`` (-1 squares to 1), 11 -> ``1``.
_WII2D_N2_DECODE = {(0, 0): "0", (0, 1): "+", (1, 0): "s", (1, 1): "1"}


def _wii2d_n2_closed_form(table: str) -> list[tuple[str, str]]:
    """Return the two-junction routes for a 2-input table, closed form."""
    t = [int(c) for c in table]
    return [
        ("-", "*"),
        (
            _WII2D_N2_DECODE[(t[0], t[2])],  # column for a zero last bit
            _WII2D_N2_DECODE[(t[1], t[3])],  # column for a one last bit
        ),
    ]


def _wii2d_symmetric_popcount_map(n: int, table: str) -> list[int] | None:
    """Return ``table`` as a function of popcount, or ``None`` if not symmetric.

    ``n + 1`` entries, ``map[p]`` the shared entry for popcount ``p``.
    """
    result: list[int | None] = [None] * (n + 1)
    for combo in range(2**n):
        p = bin(combo).count("1")
        v = int(table[combo])
        if result[p] is None:
            result[p] = v
        elif result[p] != v:
            return None
    return [v for v in result if v is not None]  # every p in 0..n is reachable


def _wii2d_parity_routes(
    n: int, popcount_map: list[int]
) -> tuple[int, list[tuple[str, str]]] | None:
    """Return the exact chain for parity or its complement, else ``None``.

    Bit 0 straight in (``('', '+')``), then ``('', '-s')`` per bit: ``-s``
    maps ``v`` to ``(v - 1)**2``, swapping 0 and 1.  XNOR swaps bit 0's branches.
    """
    if popcount_map == [p % 2 for p in range(n + 1)]:
        first = ("", "+")
    elif popcount_map == [1 - p % 2 for p in range(n + 1)]:
        first = ("+", "")
    else:
        return None
    routes = [first] + [("", "-s")] * (n - 1)
    return 0, routes


# Narrowest fold: a turn column each end, one op column between.  Narrower
# requests are raised to it, not refused.
_WII2D_MIN_FOLD_SPAN = 3


def _wii2d_fold_decode(
    decode_start: int, ops: str, span: int, first_row: int
) -> dict[tuple[int, int], str]:
    """Lay ``ops`` out as a boustrophedon below the chain, not along row 0.

    The 48-column ``+`` run to an ASCII digit folds with nothing re-derived:
    ``+`` commutes and the turn cells are accumulator-neutral.  The pointer
    leaves row 0 south on a ``v`` at ``decode_start``, past every merge,
    lands on ``first_row`` where ``<`` turns it west; a fold row carries
    ``span - 2`` ops between its two turn columns.
    """
    cells: dict[tuple[int, int], str] = {}
    row = first_row
    # The entry turn is at or east of the span, never on an op column.
    cells[(row, decode_start)] = "<"
    step = -1
    col = span - 2
    for op in ops:
        if not 1 <= col <= span - 2:
            turn = 0 if step < 0 else span - 1
            cells[(row, turn)] = "v"
            row += 1
            cells[(row, turn)] = ">" if step < 0 else "<"
            step = -step
            col = 1 if step > 0 else span - 2
        cells[(row, col)] = op
        col += step
    return cells


def _wii2d_layout(
    n: int, start: int, routes: list[tuple[str, str]], width: int | None = None
) -> list[str]:
    """Lay out the junction chain template.

    Junctions and bit-0 ops on row 0, bit-1 ops on a detour row below,
    re-merging before the next junction with no blank seam columns (they
    bought legibility at a column per program).
    """
    # A junction is one cell ('v' or '>'); nothing on row 0 follows it.
    placeholder_width = len(_WII2D_INPUT)

    placeholder_col = [0] * n
    # Column 0 is '>'; an optional start digit (always a single 0-9) takes
    # column 1.  No n <= 3 table needs one, but it gets its own column.
    placeholder_col[0] = 2 if start != 0 else 1
    merge_col = [0] * n
    for i in range(n):
        r0, r1 = routes[i]
        # Row 0: placeholder + r0; row i+1: '>' + r1.  The merge is the
        # column past the longer, the next junction the column past that.
        row0_end = placeholder_width + len(r0)
        row1_end = 1 + len(r1)
        merge_col[i] = placeholder_col[i] + max(row0_end, row1_end)
        if i + 1 < n:
            placeholder_col[i + 1] = merge_col[i] + 1

    decode_start = merge_col[n - 1] + 1  # the column past the last merge
    shift_to_ascii_digit = _ASCII_ZERO
    print_op = "~."
    flat_cols = decode_start + shift_to_ascii_digit + len(print_op)

    # The chain itself cannot fold (each detour row hangs under its own
    # junction), so the floor is the chain plus the 'v' column.  Whether to
    # fold is :func:`wii2d`'s call, on the rendered width: comparing cells
    # here once declined to fold parity at n == 6 (80 cells, 92 chars).
    folded: dict[tuple[int, int], str] = {}
    total_cols = flat_cols
    if width is not None:
        span = max(_WII2D_MIN_FOLD_SPAN, min(width, decode_start + 1))
        folded = _wii2d_fold_decode(
            decode_start, "+" * shift_to_ascii_digit + print_op, span, n + 1
        )
        total_cols = max(decode_start + 1, span)

    total_rows = max((row for row, _ in folded), default=n) + 1
    grid = [[" "] * total_cols for _ in range(total_rows)]
    grid[0][0] = ">"
    if start:
        grid[0][1] = str(start)
    for i in range(n):
        # Input i's run: one cell, either fill.
        grid[0][placeholder_col[i]] = _WII2D_INPUT
        r0, r1 = routes[i]
        for k, ch in enumerate(r0):
            grid[0][placeholder_col[i] + placeholder_width + k] = ch
        # 1-branch: descend to row i+1, travel east, ascend to the merge
        grid[i + 1][placeholder_col[i]] = ">"
        for k, ch in enumerate(r1):
            grid[i + 1][placeholder_col[i] + 1 + k] = ch
        grid[i + 1][merge_col[i]] = "^"
        grid[0][merge_col[i]] = ">"
    if folded:
        grid[0][decode_start] = "v"
        for (fold_row, fold_col), cell in folded.items():
            grid[fold_row][fold_col] = cell
    else:
        for k in range(shift_to_ascii_digit):
            grid[0][decode_start + k] = "+"
        for k, op in enumerate(print_op):
            grid[0][decode_start + shift_to_ascii_digit + k] = op
    grid[1][0] = "!"
    return ["".join(row).rstrip() for row in grid]


def wii2d(truth_table: str, width: int | None = None) -> str:
    """Build a WII2D template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.
    ``width`` lays the program out to fit (a grid cannot be reflowed): the
    48-cell digit shift folds (:func:`_wii2d_fold_decode`), the junction
    chain does not, and a width under that floor returns the narrowest
    program (71 -> 22 columns at three inputs).

    Each input is embedded once as a junction cell filled with ``>``/``v``;
    the junctions form a merging chain whose ops transform the accumulator
    into the table entry.  ``n == 2`` uses a closed form; larger ``n``
    constructs the ops (:func:`_wii2d_routes`); symmetric tables take a
    popcount chain, decoding over ``n`` points.  Three cost guards bound the
    general path: :data:`_WII2D_MAX_INDEX_DOMAIN` (via :func:`_wii2d_cost`,
    so dense tables stop at ``n == 9`` while an ``n == 8`` xor-of-a-subset
    builds in 217 chars), :data:`_WII2D_MAX_MAGNITUDE` and
    :data:`_WII2D_MAX_REAL_DOMAIN`.  A refusal raises :class:`ValueError`
    naming the bound; see the constants and the limitations ledger.
    """
    n = _validate_truth_table(truth_table)
    result = _wii2d_routes(n, truth_table)
    if result is None:
        # Report the width actually charged, not ``2 ** (n - 1)``; the two
        # bounds refuse for different reasons and say which.
        _chain, states = _wii2d_chain(n, truth_table)
        charged = _wii2d_cost(n, states)
        if charged > _WII2D_MAX_INDEX_DOMAIN:
            raise GeneratorCapError(
                f"the WII2D decode for this n == {n} table spans {charged} "
                f"points, past the {_WII2D_MAX_INDEX_DOMAIN}-point cost "
                f"guard; below the bound this "
                "is a size/time policy, but raising the constant does not "
                "buy the next doubling -- a domain-512 decode ratchets (live "
                "512 -> 475 over 19 steps, bit length doubling every step) "
                "and refuses on the magnitude bound anyway.  See "
                "the limitations ledger: dense n == 10 is a wall of the exactly-once "
                "embed convention"
            )
        real = _wii2d_real_domain(states)
        if real > _WII2D_MAX_REAL_DOMAIN:
            raise GeneratorCapError(
                f"the WII2D chain for this n == {n} table leaves a decode "
                f"domain of {real} points, past the "
                f"{_WII2D_MAX_REAL_DOMAIN}-point width guard; the table is "
                "inside "
                "the arity-scale cost guard but its chain found no merge, so "
                "the decode would be too wide to be worth emitting (see "
                "the limitations ledger)"
            )
        raise GeneratorCapError(
            "the WII2D n-embedding construction found no route: a branch "
            "decode ratcheted past the magnitude bound or ran out of legal "
            "folds; at the domains the guards admit this is the rare "
            "doubling-trap pattern (about 1 in 10 sampled at domain 256), "
            "refused promptly rather than left to diverge"
        )
    start, routes = result
    flat = "\n".join(_wii2d_layout(n, start, routes, None))
    if width is None or max(len(line) for line in flat.split("\n")) <= width:
        return flat
    # Rendered width, which is the program's: a junction cell is one char.
    return "\n".join(_wii2d_layout(n, start, routes, width))
