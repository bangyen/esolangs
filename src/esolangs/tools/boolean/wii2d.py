"""Boolean-function generator for WII2D (parameterized convention).

WII2D is a no-input grid language, so this follows the parameterized
convention described in :mod:`esolangs.tools.boolean.parameterized`: the
template's ``{Xi}`` placeholders are junction cells the harness fills with
``>`` (bit 0) or ``v`` (bit 1), one program per input combination.

The branch op strings are *constructed*, not searched.  Both halves are
single deterministic passes with no backtracking: :func:`_wii2d_chain` walks
the table's decision diagram one input at a time, taking the first legal
junction pair from a fixed catalogue (Horner is always legal, so the walk
cannot fail), and :func:`_wii2d_decode` folds the surviving values down by
taking the single best fold at each step.  Nothing keeps alternatives,
widens a beam, or retries, so the program is a direct function of the table.
"""

import heapq
import re

from esolangs.tools.boolean.helpers import _ASCII_ZERO, _validate_truth_table

__all__ = ["wii2d"]


# --- WII2D (no-input grid language; parameterized convention) ---
#
# WII2D's only I/O is the ``~`` output; it has no input command, so the
# boolean generator follows the parameterized convention: the template's
# ``{Xi}`` placeholders are junction cells, and the harness instantiates one
# program per input combination by filling each placeholder with ``>`` (bit
# 0, the pointer continues east) or ``v`` (bit 1, the pointer turns south).
#
# A full decision tree would need each input re-embedded at every node of its
# level (2**n - 1 junctions), since the pointer visits each junction at most
# once, but WII2D has no memory to store each input once and re-read it the
# way the tape/register parameterized generators (``bio``/``back``/``ram0``)
# do.  Instead :func:`wii2d` exploits the accumulator arithmetic: the
# junctions form a *merging chain* (each branch's op cells transform the
# accumulator and the branches re-merge before the next junction), so each
# input is embedded exactly once and the final accumulator decodes to the
# table entry.
#
# Nothing here searches.  WII2D has no accumulator-conditional control flow
# -- ``^v<>`` are static cells the harness fills -- so a junction's two op
# strings are shared by every prefix that reaches it.  That pins the
# construction down to one shape: the chain can only accumulate the bits into
# a single number, and a final op string has to turn that number into the
# table entry.  :func:`_wii2d_routes` does exactly that, in two constructed
# halves.
#
# The chain accumulates the table's *decision diagram node*, not simply an
# index.  Two prefixes that leave the same residual function may share an
# accumulator value, and :data:`_WII2D_JUNCTIONS` prefers the pairs that make
# them: merging keeps the surviving value set small, which hands the final
# decode a narrower domain than the ``2 ** (n - 1)`` index would.  Horner's
# ``('*', '*+')`` is the last entry and merges nothing, which is what makes
# the walk total -- see :data:`_WII2D_JUNCTIONS` for why it is always legal.

# The op alphabet the construction draws on: digits set the accumulator,
# ``+ - * / s`` are arithmetic (increment, decrement, double, halve, square),
# and a space is a no-op.  Only ``s`` is not order-preserving, which is why
# the decode below is built out of folds around it.

# The fold rule is deterministic: at every step :func:`_wii2d_decode` takes
# the single best candidate :func:`_wii2d_folds` offers, under a fixed
# ranking (smallest magnitude, then fewest live values, then shortest op
# string).  There is no beam, no width ladder, and no retry pass -- one
# candidate is taken at each step and the decode is whatever that chain of
# choices produces.
#
# The fold only *reshapes*; :func:`_wii2d_compress` is what merges, by
# steering an add-then-halve run's shift onto collisions.  That split is
# what carries the wide domains: dense ``D == 256`` decodes 18 of 20
# sampled patterns where the one-level halving it replaced managed 3 of 10.
#
# That this suffices is not an assumption: it is exhaustive over every 0/1
# pattern through ``D == 16``, the widest domain the general path asks for,
# verified by applying the emitted op string back over the domain.  See
# ``docs/wii2d_generator.md``.

# The widest fold centre worth emitting.  A centre costs ``abs(c)`` cells --
# ``'-' * c`` is spelled out in the grid -- so this is a bound on program
# width, not on the arithmetic: a fold at 10**6 is perfectly correct and
# utterly useless, since the row it lands on is a million columns long.
#
# Compression normally keeps the centres tiny (the medians below 100 columns
# come out of it), and this only rejects the outliers where a fold sequence
# has drifted somewhere it cannot come back from.  Rejecting them costs
# nothing: the ranking promotes the next candidate, and every pattern through
# ``D == 16`` still decodes.  Ranking by magnitude first (see
# :func:`_wii2d_folds`) means the rejected outliers are the ones the rule was
# already avoiding.
_WII2D_MAX_CENTRE = 4096

# The largest live-value magnitude a decode may reach before it is aborted
# as diverging.  This is a divergence certificate, not a step budget: on
# every table that builds, the fold's spread-then-recoup cycle holds the
# live values small -- max 1922 over the 532-table corpus, max 13499 over
# eight sampled domain-256 patterns -- while a failing decode *ratchets*,
# roughly doubling its bit length every step (a sampled domain-512 run
# climbed 14 -> 670597 bits with every candidate enumerated), so a state
# past this bound never comes back.  2**20 sits 78x above the largest
# success.
#
# **This bound is load-bearing.**  It does not merely anticipate a stop the
# centre cap would reach anyway: with it lifted, ratcheting domain-256
# patterns do not stop at all.  Three sampled tables that abort here in
# 0.45-1.59s ran 136s, 183s and 214s unbounded, reaching bit lengths of
# 299526, 1173459 and 644663 and still climbing.  Without this check the
# 256 guard would ship hangs, so it is what makes a refusal prompt rather
# than a property of the sample.  The check is on the state, not the
# candidates, so it cannot change which candidate a succeeding table takes;
# and it is deterministic where a wall-clock budget would make the program
# depend on the machine.
_WII2D_MAX_MAGNITUDE = 1 << 20

# How many candidate folds are compressed before the true ranking is applied.
#
# Compression is the expensive half of a candidate -- a per-depth arc scan
# over every close pair -- and the decode takes only the head, so
# compressing every candidate is work thrown away.
#
# The screen cannot be a *bound*.  Compression is a contraction, so the
# uncompressed magnitude says almost nothing about the compressed one, and no
# early exit justified that way preserves the answer.  This is an admitted
# approximation: the shortlist is ranked on the uncompressed state, and only
# its members get the real key.
#
# Eight, raised from four when the steered compression landed.  The two
# are measured together: the compression rewrite at shortlist 4 emits
# 286669 characters over the 532-table corpus, marginally *worse* than the
# 285903 the one-level walk emitted, and only widening the shortlist to 8
# turns it into a win at 261019 (-8.7%).  Steering makes a candidate's
# compressed magnitude much less predictable from its uncompressed one, so
# the screen has to keep more of them to find the good ones.
_WII2D_SHORTLIST = 8

# How many legal shifts a compression run examines per depth.  The legal
# set is exact (the arc-union complement); this only caps how many of its
# members are scored for merges, taking the first few values of each gap
# so the smallest legal shift is always among them.  An admitted
# approximation with the same status as the shortlist above.
_WII2D_SHIFT_SAMPLES = 40

# The widest decode domain the general (non-symmetric) path will attempt, so
# that path is used up to ``n == 9`` by default.
#
# **This is a cost policy, not a capability bound**, and it is charged
# against :func:`_wii2d_cost` -- the smaller of ``2 ** (n - 1)`` and the
# domain the chain actually leaves -- rather than against the worst case
# alone.  That distinction is what makes structured tables reachable at any
# arity: an ``n == 8`` xor-of-a-subset collapses to a 4-point decode and
# builds in 217 characters, which the old worst-case-only check refused
# without ever looking at it.
#
# What the constant buys is bounded *width*, which still grows as the domain
# doubles.  Symmetric tables never reach this check: they decode over ``n``
# points via the popcount chain.  ``docs/wii2d_generator.md`` has the measured
# width and time tables this value was chosen against.
#
# 256 admits dense ``n == 9`` *usually*: the deterministic witness table
# (sha256-derived, see the grid tests) builds in 1.1s at 78362 characters
# with all 512 rows executed against the interpreter.  Every sampled failure
# *returns* -- an aborted ratchet or a fold dead-end -- so a refusal is
# prompt rather than a hang, which is what made this raise from 128 safe;
# :data:`_WII2D_MAX_MAGNITUDE` makes that promptness a guarantee instead of
# a sample.  ``docs/wii2d_generator.md`` carries the resampled build and
# refusal curves.
#
# Dense ``n == 10`` (domain 512) stays refused, and *not* because the number
# is 256.  Raised to 512 the witness table still refuses, in 0.8s per
# branch: with the magnitude bound lifted its decode ratchets, the live
# count crawling 512 -> 475 over 19 steps while the bit length doubles every
# step, 9 -> 1089888 bits, the 19th step alone 144s.  Full enumeration is no
# better -- 512 -> 373 over 19 steps past 670000 bits.  So the next doubling
# is a wall of the fold algebra under the exactly-once embed convention, not
# a budget choice -- see ``docs/wii2d_generator.md``.
_WII2D_MAX_INDEX_DOMAIN = 256

# The widest *real* chain domain any table may decode over, whatever the
# arity-scale guard above allows.
#
# These two bound different things.  ``_WII2D_MAX_INDEX_DOMAIN`` is charged
# the *minimum* of the worst case and the real domain, so a table whose chain
# collapses is judged on what it actually costs.  But the minimum also means
# a table can be admitted on its worst case while its real domain runs away:
# with no merge available the walk falls through to Horner, and a non-merging
# pair can leave a domain far *above* ``2 ** (n - 1)``.
#
# Measured, that overshoot is rare but unbounded, so this is the same policy
# as :data:`_WII2D_MAX_CENTRE` one level up: correct, but too wide to be worth
# emitting.  256 sits above every overshoot measured to decode and below the
# one that does not.  ``docs/wii2d_generator.md`` has both figures and why
# refusing the latter is not a regression.
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

    Returns ``None`` when two inputs have collapsed onto the same value but
    need different bits -- an unrecoverable state, since nothing downstream
    can separate two inputs that share an accumulator value.
    """
    seen: dict[int, int] = {}
    for value, bit in zip(values, bits, strict=True):
        if seen.get(value, bit) != bit:
            return None
        seen[value] = bit
    return seen


def _wii2d_legal_shifts(arcs: list[tuple[int, int]], block: int) -> list[int]:
    """Return up to :data:`_WII2D_SHIFT_SAMPLES` legal shifts, ascending.

    ``arcs`` are the bad cyclic intervals ``(start, length)`` modulo
    ``block``; a legal shift is any value outside their union.  The gaps
    between merged arcs are walked in order and the first few values of
    each are taken, so the result is deterministic and the smallest legal
    shift always leads.
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

    A run of ``k`` halvings with an optional ``+`` before each is exactly
    ``v -> (v + S) // 2**k``, ``S`` the shift bits read in emission order
    (the nested-floor identity), so the whole family is searched directly
    rather than one halving at a time.  Two values land in one block --
    merging if they need the same bit, fatal if not -- exactly when ``S``
    falls in a cyclic arc, so each different-bit pair at gap ``g < 2**k``
    forbids ``2**k - g`` shifts and the legal shifts are the complement of
    the arc union.  Legality is monotone: a legal depth-``k`` run stays
    legal truncated to ``k - 1``, so the depth scan stops at the first
    empty level.

    The choice is a fixed rule, not a search: take the ``(k, S)`` that
    merges the most values, deepest run then smallest shift on ties, and
    repeat until no halving is legal.  Steering ``S`` toward collisions is
    what makes compression the engine's *merging* half -- the fold only
    reshapes the values so that same-bit values can land in one block --
    and it is what carries dense domains past the squaring blow-up that a
    greedy one-level halving walks into (see ``docs/wii2d_generator.md``).
    Each applied run strictly shrinks the span, so this terminates.
    """
    while True:
        live = _wii2d_points(values, bits)
        if live is None:  # pragma: no cover - callers pass legal states
            return values, ops
        points = sorted(live)
        span = points[-1] - points[0]
        # ``max(abs(v)) <= 1`` is the old one-level walk's stop, kept: a
        # small span at a large magnitude still shrinks (every applied run
        # strictly lowers the maximum for values past 1), and stopping on
        # span alone would hand the threshold thousand-character offsets.
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

    With a single value left the answer is a constant, so a digit does it.
    With two, ``x -> (x - t) // 2 ** k`` is a step function: subtracting the
    upper value leaves the lower one negative, and halving drives every
    negative to -1 (floor division rounds toward minus infinity) and leaves 0
    at 0, so a following ``+`` reads out the indicator ``[x >= t]``.  ``-s``
    flips it when the bits run the other way.
    """
    points = sorted(live)
    if len(points) == 1:
        return str(live[points[0]])
    low, high = points
    if live[low] == live[high]:
        # Two values, one answer: a digit resets both.  Reachable when
        # compression stops at ``{0, 1}`` under one label; the indicator
        # below would answer (0, 1) or (1, 0), never (c, c).
        return str(live[low])
    # after the subtraction the values are ``low - high`` and 0, so the
    # halving run only has to be long enough to bottom that span out at -1.
    runs = max(abs(low - high).bit_length() + 1, 1)
    indicator = _wii2d_offset(high) + "/" * runs + "+"
    if live[low] == 0 and live[high] == 1:
        return indicator
    return indicator + "-s"


def _wii2d_folds(
    values: list[int], bits: list[int]
) -> list[tuple[int, int, int, str, list[int]]]:
    """Return the candidate folds from this state, best first.

    ``s`` is the only op that is not order-preserving, and ``'-' * c + 's'``
    sends ``x`` to ``(x - c) ** 2``, which merges exactly the pairs
    equidistant from ``c``.  That is the whole trick: it is the one way to
    make two different accumulator values agree without a conditional, so
    every fold is one step toward the two values a threshold can read.  A
    fold is legal only when every pair it merges needs the same bit.
    Doubling first (``*``) makes every gap even, which opens the midpoints
    that are otherwise half-integral.

    Only the first :data:`_WII2D_SHORTLIST` candidates are compressed, ranked
    on their uncompressed state; the rest are dropped unseen.  That screen is
    an approximation rather than a bound -- see the constant -- and it is
    what keeps the per-step cost flat as the domain grows.
    """
    # Enumerate the legal folds first, *uncompressed*, and by pair rather
    # than by centre.  ``(p - c) ** 2`` collides for exactly the pairs
    # symmetric about ``c``, so a centre is illegal iff some pair summing to
    # ``2c`` needs two different bits, and the merged count is the live count
    # less the number of pairs summing to ``2c`` (at most two points share
    # one ``abs(p - c)``, so those pairs are disjoint).  Reading the pair sums
    # off once therefore replaces the per-centre rescan of the whole domain,
    # dropping the step from ``O(P ** 3)`` to ``O(P ** 2)`` -- 5.6s of the
    # 6.3s dense ``n == 9`` build was this loop.  The candidate set is
    # unchanged: a centre whose only even-sum pairs cross the bits is exactly
    # one the rescan rejected, so legal centres always come from a same-bit
    # pair.
    #
    # Compression stays the expensive half -- a halving loop over the whole
    # domain, each step rebuilding the live map -- and the caller only ever
    # takes the head, so only the shortlist is compressed and only its
    # members' folded values are materialized.
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
        # sorted, not raw dict order: ties in the ranking below are broken by
        # the order candidates were appended, so iterating unordered would let
        # the emitted program depend on hash order rather than on the table.
        for double in sorted(merging):
            if double % 2 or double in crossing:
                continue
            centre = double >> 1
            if abs(centre) > _WII2D_MAX_CENTRE:
                continue  # correct but too wide to spell out in the grid
            # The shortlist key, on the uncompressed state.  It is a
            # *screen*, not the ranking: compression can lower a magnitude by
            # an order of magnitude (529 to 17 is real), so this cannot
            # predict the true order and is not used as it.  The squares are
            # monotone in the distance from the centre, so the widest folded
            # value is always one of the two span ends.
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
    # Magnitude first.  A fold centre is spelled out as ``'-' * c``, so the
    # live values *are* the program's width: keeping them small is what
    # keeps the emitted grid small.  Ranking survivors first instead reaches
    # the same two-value state through much larger numbers -- 396131
    # characters against 285903 over the 532-table corpus, a 39% regression
    # -- which holds against the steered compression below just as it held
    # against the one-level halving it replaced.
    out.sort(key=lambda cand: (cand[1], cand[0], cand[2]))
    return out


def _wii2d_decode(pattern: list[int]) -> str | None:
    """Construct an op string realizing ``pattern`` on ``0 .. len(pattern)-1``.

    This is the one primitive the general path needs, and it is a
    construction rather than a search: from the starting state it repeatedly
    takes the *single* best fold :func:`_wii2d_folds` offers, until two live
    values remain, and reads those out with a threshold
    (:func:`_wii2d_threshold`).  No alternative is kept, so nothing
    backtracks -- the op string is a direct function of the table.

    The step count is bounded a priori.  A fold merges at least one pair, so
    the live-value count strictly drops at every step, putting the loop at no
    more than ``len(pattern)`` iterations; each step costs a fixed
    enumeration of midpoints.  That makes the decode effectively constant
    time for the domains the generator asks for, instead of the
    beam-width-and-retry ladder this replaced.

    Returns ``None`` only if some step offers no legal fold at all.  No
    pattern through ``D == 16`` -- the widest domain the general path asks
    for -- does; see the note above :data:`_WII2D_MAX_CENTRE`.
    """
    bits = list(pattern)
    if all(bit == bits[0] for bit in bits):
        return str(bits[0])  # constant: a digit is the whole decode
    values, ops = _wii2d_compress(list(range(len(bits))), bits, "")
    # A fold strictly reduces the live-value count, so this cannot run longer
    # than there are values to merge; the bound is a guard, not a budget.
    for _ in range(len(bits) + 1):
        live = _wii2d_points(values, bits)
        if live is None:
            return None
        # The ratchet abort: a state past the bound is diverging, not slow,
        # so give up rather than let the fold double its bit length forever.
        # See :data:`_WII2D_MAX_MAGNITUDE` for the measured separation.  It
        # sits ahead of the two-live exit so the threshold's ``'-' * c``
        # spelling is bounded too, not just the fold chain.
        if max(abs(v) for v in values) > _WII2D_MAX_MAGNITUDE:
            return None
        if len(live) <= 2:
            return ops + _wii2d_threshold(live)
        candidates = _wii2d_folds(values, bits)
        if not candidates:
            return None
        # _wii2d_folds returns candidates best-first under the fixed ranking,
        # so taking the head is the whole choice -- no width to widen.
        *_rank, fragment, folded = candidates[0]
        values, ops = folded, ops + fragment
    return None


# The op-string pairs the chain draws its junctions from, in merge order:
# the arithmetic offsets, then the digit and square merges, then the halving
# ones, with Horner last.
#
# The order is *semantic*, not by cost, and the difference is measurable: it
# holds 42 total-character inversions, the plainest being ``('', '0')`` at
# one character sitting behind six two-character entries.  No sort key
# reproduces it -- a sweep of 1.9M candidates over 63 features (field
# lengths, per-character counts, weighted op costs, and their 1-to-3-deep
# lexicographic compositions, both directions) found none monotone along the
# shipped sequence, against a positive control that recovers 172 keys for a
# deliberately sorted list.  Two adjacent pairs make that a proof rather
# than a failed search: index 10 to 11 and index 17 to 18 both *descend* in
# length, so no key monotone in total length can order this table.
#
# What the order buys is size, and it was tuned rather than derived:
# permuting the merge entries (Horner pinned last) changes 360 of 392
# emitted programs with zero errors, and the shipped order beats 7 of 8
# random permutations on total size (57708 against up to 59557).  So it is a
# measured preference over a structure that is already total -- reordering
# costs characters, never correctness.
#
# A chain junction is a pair ``(A, B)``: ``A`` transforms the accumulator
# when the input is 0, ``B`` when it is 1.  The pair is shared by every path
# reaching that junction -- WII2D has no accumulator-conditional control
# flow, so a junction cannot act on the bits already read -- which is the
# constraint the whole construction lives under.
#
# Horner ``('*', '*+')`` sits last as the *total* fallback: it is legal at
# every level unconditionally.  The chain's invariant is that two distinct
# cofactors never share an accumulator value (they need different futures
# but would be indistinguishable).  Under Horner the children are ``2v`` and
# ``2w + 1``, which differ in parity, and ``2v == 2w`` forces ``v == w``,
# which the invariant already forbids -- so the invariant is preserved and
# there is always at least one legal pair.  Nothing here can dead-end.
#
# The earlier entries are the ones that *merge*: when two paths reach the
# same residual function they can share a value, keeping the surviving value
# set small and handing the final decode a narrower domain.  They are tried
# in a fixed order and the first legal one is taken, so the chain is a single
# pass with no backtracking and the program depends only on the table.
#
# That order is semantic, not by cost: ``('', '0')`` is one character and
# still sits after three two-character entries, and sorting by total
# characters -- with or without reset/star tiering, or a weighted op cost --
# reproduces none of it.  It is a tuned preference over a set every member of
# which is correct, so permuting it is a size regression rather than a bug:
# permuting the twenty merge entries (Horner pinned last) changes 360 of 392
# emitted programs with zero errors, and the shipped order beats 7 of 8
# random permutations on total size.  Reordering therefore means re-running
# that tuning, not just re-checking the tests.
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

    A state is a ``(cofactor, value)`` pair: the residual truth table still
    to be decided, and the accumulator value the paths reaching it carry.
    Reading a bit splits each cofactor into its two halves and applies the
    matching op string to the value.

    The pair is illegal exactly when it lands two *different* cofactors on
    one value.  Nothing downstream could separate them -- the accumulator is
    the machine's only state -- so the caller moves on to the next pair.  Two
    paths reaching the *same* cofactor on one value is the opposite: the
    merge that makes this chain narrower than Horner's.
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
            # The decode indexes its pattern by accumulator value, so a
            # negative has no slot.  Rejecting it here rather than at the end
            # keeps the chain's values in ``0 .. 2 ** n``, which is what lets
            # :func:`_wii2d_columns` be total.
            return None
        if seen.setdefault(value, cofactor) != cofactor:
            return None
    return out


def _wii2d_chain(
    n: int, table: str
) -> tuple[list[tuple[str, str]], list[tuple[str, int]]]:
    """Build the first ``n - 1`` junctions and the states they leave.

    Walks the table's decision diagram one input at a time, taking the first
    legal pair from :data:`_WII2D_JUNCTIONS` at each level.  Since Horner is
    always legal the walk never fails, so this returns a chain rather than an
    optional one.
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

    Each surviving cofactor is two entries wide -- one input left to read --
    so branch 0 must answer its first entry and branch 1 its second.  The
    patterns are indexed by accumulator value, and the values are dense from
    zero only under Horner, so the caller decodes over ``0 .. max``.
    """
    width = max(value for _, value in states) + 1
    # Values are non-negative -- :func:`_wii2d_advance` refuses a pair that
    # would make one -- so every state has a slot.  Unreached slots keep the
    # zero they are filled with: no state carries those values, so the entry
    # is a don't-care the decode may satisfy however it likes.  It costs a
    # little size and no correctness.
    low = [0] * width
    high = [0] * width
    for cofactor, value in states:
        low[value] = int(cofactor[0])
        high[value] = int(cofactor[1])
    return low, high


def _wii2d_real_domain(states: list[tuple[str, int]]) -> int:
    """Return the decode domain the chain walk actually left.

    The columns are indexed by accumulator value, so the domain is one past
    the largest surviving value -- not the number of live states, which may
    be far smaller when the values are sparse.
    """
    return max(value for _cofactor, value in states) + 1


def _wii2d_cost(n: int, states: list[tuple[str, int]]) -> int:
    """Return the decode width :data:`_WII2D_MAX_INDEX_DOMAIN` is charged.

    The guard used to compare against ``2 ** (n - 1)`` alone, computed
    *before* the chain was walked.  That is the wrong number in both
    directions, so this charges the smaller of the worst case and the domain
    the walk actually left.

    *The real domain can be far narrower.*  The chain's merging junctions
    collapse structured tables well below the worst case, and the old check
    refused them without ever looking.  Measured at ``n == 7``, where the
    worst case is 64 and every table was refused outright: a function of
    three of the inputs leaves a domain of 3 or 4, an xor-of-a-subset 4 or 5,
    a weighted threshold 7 to 12, a mux 24 to 32.  Those build in 186 to 339
    characters -- smaller than a typical ``n == 6`` program -- and each was
    run through the interpreter on all 128 input combinations.  ``n == 8``
    reaches the same way.

    *The real domain can also be wider.*  With no merge available the walk
    falls through to Horner, and a non-merging pair can leave a domain
    *above* ``2 ** (n - 1)``: sampled random tables overshoot in 0.5% of
    cases at ``n == 5`` (domain 37 against a worst case of 16) and 0.2% at
    ``n == 6`` (domain 197 against 32).

    Charging the real domain alone would *refuse* those overshoot tables,
    which the worst-case check had always accepted -- and they are not
    failures: the decode succeeded on both branches in every overshoot
    sampled.  Taking the minimum keeps the old contract exactly (anything
    ``2 ** (n - 1)`` admitted is still admitted) and adds the narrow-domain
    tables on top, so the change is additive.
    """
    worst_case: int = 2 ** (n - 1)
    return min(worst_case, _wii2d_real_domain(states))


def _wii2d_routes(n: int, table: str) -> tuple[int, list[tuple[str, str]]] | None:
    """Construct the per-junction branch op strings realizing ``table``.

    A junction chain of length ``n`` (one per input) computes

        acc = R[n-1][b_n-1] ( ... R[0][b_0] ( start ) ... )

    for each input combo, where each ``R[i][b]`` is an op string applied when
    input ``i`` takes value ``b``.  Since no op string can depend on the bits
    already read, the construction splits the work in two:

    * **Chain.**  Junctions 0 through ``n - 2`` come from
      :func:`_wii2d_chain`, which walks the table's decision diagram and
      takes the first legal pair from :data:`_WII2D_JUNCTIONS` at each level.
      The accumulator ends up naming the residual function still to be
      decided, not merely an index: where two prefixes leave the *same*
      residual function the walk lets them share a value.  With no merges
      available it falls through to Horner's ``('*', '*+')`` and the value is
      exactly ``q``, the integer whose bits are the first ``n - 1`` inputs.
    * **Decode.**  The last junction's two branches read the surviving
      values: branch ``b`` must map each value to the entry its residual
      function gives for a final bit of ``b``.  Each is a 0/1 pattern over
      ``0 .. max value``, which :func:`_wii2d_decode` constructs.  Merging
      makes that domain narrower than the ``2 ** (n - 1)`` an index would
      give, and never wider.

    A *symmetric* table (one depending only on how many inputs are set)
    short-circuits ahead of the chain: junctions 0 through ``n - 2`` use
    ``('', '+')``, so the accumulator is the popcount of the bits read so
    far, and the last junction decodes over ``n`` points.  ``('', '+')`` is a
    catalogue pair too, but taking it directly skips the diagram walk and
    guarantees the popcount domain rather than merely allowing it.  Same
    decode primitive, exponentially smaller domain -- which keeps
    majority-of-n and the other threshold functions reachable at arities
    where the index chain's decode would be hopeless.

    ``n == 2`` uses a closed form (:func:`_wii2d_n2_closed_form`) and parity
    gets an exact O(1) one (:func:`_wii2d_parity_routes`); both are shorter
    than the general construction, so they stay.
    """
    if n == 2:
        return 0, _wii2d_n2_closed_form(table)
    popcount_map = _wii2d_symmetric_popcount_map(n, table)
    if popcount_map is not None:
        parity_result = _wii2d_parity_routes(n, popcount_map)
        if parity_result is not None:
            return parity_result
        # branch b of the last junction sees popcount p of the first n - 1
        # bits and must answer for a total popcount of p + b.
        low = _wii2d_decode(popcount_map[:n])
        high = _wii2d_decode(popcount_map[1:])
        if low is not None and high is not None:
            return 0, [("", "+")] * (n - 1) + [(low, high)]
    # Walk the chain *before* the cost guard: the walk is microseconds (a
    # fixed catalogue scan per level, no search), so charging the domain it
    # actually leaves costs nothing.  See :func:`_wii2d_cost`.
    chain, states = _wii2d_chain(n, table)
    # Refused on cost, not on capability: the decode is never attempted at
    # either width.  Sampled decodes past the first bound do succeed -- see
    # the constants for what each one charges and why.
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


# For n == 2 a closed form exists: ``R0 = (-, *)`` packs bit 0 as -1 (a zero
# bit) or 0 (a one bit), and each branch of the last junction decodes one of
# the table's two columns from that packed value.  On the pair (-1, 0) the
# column pattern maps to a single op: both zero -> the digit 0, 0 then 1 ->
# ``+``, 1 then 0 -> ``s`` (squaring sends -1 to 1), both one -> the digit 1.
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

    A table is symmetric when every combo with the same number of set bits
    has the same entry (the language's version of a boolean function that
    doesn't care which inputs are set, only how many).  The returned list has
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

    Parity chains bit 0 straight in (``('', '+')``), then folds every later
    bit with ``('', '-s')``: ``-s`` sends the running value ``v`` to
    ``(v - 1)**2``, which maps 0 -> 1 and 1 -> 0, so a zero bit leaves the
    running parity alone and a one bit flips it, keeping the value in
    ``{0, 1}`` throughout.  The complement (XNOR-of-n) swaps bit 0's branches
    so the chain starts from the flipped bit instead.
    """
    if popcount_map == [p % 2 for p in range(n + 1)]:
        first = ("", "+")
    elif popcount_map == [1 - p % 2 for p in range(n + 1)]:
        first = ("+", "")
    else:
        return None
    routes = [first] + [("", "-s")] * (n - 1)
    return 0, routes


# The narrowest fold that makes progress: a turn column at each end and one
# op column between them.  A width below this is raised to it rather than
# refused, matching the width plumbing everywhere else.
_WII2D_MIN_FOLD_SPAN = 3


def _wii2d_fold_decode(
    decode_start: int, ops: str, span: int, first_row: int
) -> dict[tuple[int, int], str]:
    """Lay ``ops`` out as a boustrophedon below the chain, not along row 0.

    The decode's tail is a straight run of ``+`` -- the shift to an ASCII
    digit, 48 columns of it -- followed by ``~.``.  A straight run of one
    commutative op is exactly what a fold turns from columns into rows, and
    this one folds with nothing re-derived: ``+`` commutes, so the order the
    run is walked in cannot matter, and the cells a turn spends are
    accumulator-neutral, since :func:`_accumulate` returns the accumulator
    unchanged for ``v``, ``<``, ``>`` and for the blanks the pointer crosses
    on its way down.  The value that reaches ``~`` is therefore the value
    the flat run would have reached.

    The pointer leaves row 0 heading south on a ``v`` at ``decode_start``,
    falls through the detour rows -- blank at that column, which is past
    every merge -- and lands on ``first_row``, where a ``<`` turns it west.
    Columns 0 and ``span - 1`` are turn columns and the ops go between them,
    so a fold row carries ``span - 2`` of them.
    """
    cells: dict[tuple[int, int], str] = {}
    row = first_row
    # The entry turn sits at the column the pointer falls down, which is at
    # or east of the span, so it never lands on an op column.
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

    ``{Xi}`` placeholders on row 0, each branch's op cells on row 0 (bit 0)
    or on a dedicated detour row below (bit 1), re-merging before the next
    junction.  Nothing is spaced apart: a merge sits directly on the column
    past the longer branch, the next junction directly past the merge, and
    the decode directly past the last merge.  The layout used to leave one
    blank column at each of those seams, but a blank column carries only
    straight eastward travel -- the pointer arrives at the same cell either
    way -- so it bought template legibility at the cost of width in every
    emitted program.
    """
    # A junction is a single cell: the fill writes 'v' to take the 1-branch
    # or '>' to continue east, and nothing on row 0 occupies the column after
    # it.  The '{Xi}' spelling is four characters only because that is how
    # the placeholder is written, and instantiation gives the rest back.
    placeholder_width = 1

    placeholder_col = [0] * n
    # column 0 is always '>'; a start digit (the construction only ever
    # returns a single digit 0-9) sits at column 1 with the first placeholder
    # at column 2.  With no digit the placeholder starts right after the '>'.
    # (No table found at n <= 3 needs a nonzero start, so this is the
    # untravelled branch -- but the digit's column is its own, not the
    # junction's.)
    placeholder_col[0] = 2 if start != 0 else 1
    merge_col = [0] * n
    for i in range(n):
        r0, r1 = routes[i]
        # row 0 runs placeholder, then r0, ending at placeholder_col[i] +
        # placeholder_width + len(r0); row i+1 runs '>', then r1, ending at
        # placeholder_col[i] + 1 + len(r1).  The merge sits on the first
        # column past whichever row runs longer, and the next junction on
        # the first column past the merge.
        row0_end = placeholder_width + len(r0)
        row1_end = 1 + len(r1)
        merge_col[i] = placeholder_col[i] + max(row0_end, row1_end)
        if i + 1 < n:
            placeholder_col[i + 1] = merge_col[i] + 1

    decode_start = merge_col[n - 1] + 1  # the column past the last merge
    shift_to_ascii_digit = _ASCII_ZERO
    print_op = "~."
    flat_cols = decode_start + shift_to_ascii_digit + len(print_op)

    # The chain cannot fold -- each junction is where one input is embedded
    # and each detour row hangs beneath its own junction -- so the narrowest
    # program this builds is the chain plus the one column the 'v' leaves
    # on.
    #
    # Whether to fold at all is *not* decided here, and that is the point.
    # ``flat_cols`` counts grid cells, while the program's width is counted
    # in characters -- and a junction cell holds a ``{Xi}`` placeholder,
    # which is four characters wide in the template.  Comparing the
    # requested width against the cell count declined to fold programs that
    # rendered well past it: parity at ``n == 6`` is 80 cells and 92
    # characters, so a request for 80 came back at 92.  :func:`wii2d`
    # measures the rendered flat form and only asks for a fold when that is
    # too wide, so this folds whenever it is given a width.
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
        # The junction's one cell, spelled out once the layout is finished:
        # the placeholder's four characters are how it is written, not the
        # room the junction needs, and the fill gives the difference back.
        grid[0][placeholder_col[i]] = "\x00" + str(i) + "\x00"
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
    rows = ["".join(row).rstrip() for row in grid]
    return [
        re.sub("\x00(\\d+)\x00", lambda m: "{X" + m.group(1) + "}", row) for row in rows
    ]


def wii2d(truth_table: str, width: int | None = None) -> str:
    """Build a WII2D template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    ``width`` lays the program out to fit that many columns rather than
    reflowing it afterwards, which a grid cannot be.  What folds is the
    48-cell run that shifts the answer to an ASCII digit -- a straight run
    of one commutative op, so the fold needs nothing re-derived; see
    :func:`_wii2d_fold_decode`.  What does not fold is the junction chain,
    since each junction is where one input is embedded and each detour row
    hangs beneath its own junction, so the chain's length plus one column is
    the floor.  A width under it returns the narrowest program rather than
    refusing, and a width at or above the unfolded form returns exactly what
    no width returns.  At three inputs that is 71 columns down to 22.

    WII2D has no input command, so this is a parameterized generator: the
    template's ``{Xi}`` placeholders are junction cells that the harness
    fills with ``>`` (bit 0) or ``v`` (bit 1), one program per input
    combination.  Each input is embedded exactly once: the junctions form a
    *merging chain* whose branch op cells transform the accumulator, so the
    final accumulator is the table entry (printed as ``'0'``/``'1'`` after a
    48-shift).

    Two inputs use a closed form (:func:`_wii2d_n2_closed_form`): bit 0 is
    packed as -1/0 and each column of the table is decoded by a single op.
    Larger ``n`` *constructs* the branch op strings rather than searching for
    them (:func:`_wii2d_routes`): the first ``n - 1`` junctions accumulate the
    inputs into an index by Horner's rule, and the last junction's two
    branches decode that index into the table's two columns by folding
    (:func:`_wii2d_decode`).  The construction is deterministic and depends
    only on the table, so the same table yields the same program everywhere.

    Symmetric tables (those depending only on how many inputs are set) take a
    popcount chain instead, decoding over ``n`` points rather than
    ``2 ** (n - 1)``; that keeps majority-of-n and friends cheap at arities
    well past where the general path stops.

    Two **cost guards** bound the general path, neither a claim about what
    the construction can represent.  :data:`_WII2D_MAX_INDEX_DOMAIN` charges
    :func:`_wii2d_cost`, the smaller of ``2 ** (n - 1)`` and the domain the
    chain actually leaves, so dense tables run out at ``n == 9`` while
    *structured* ones keep going at any arity: an ``n == 8`` xor-of-a-subset
    collapses to a 4-point decode and builds in 217 characters.  Inside the
    admitted domains a rare pattern still ratchets into the doubling trap;
    :data:`_WII2D_MAX_MAGNITUDE` refuses those in seconds instead of
    diverging.
    :data:`_WII2D_MAX_REAL_DOMAIN` then refuses the rare table admitted on
    its arity whose chain found no merge at all, leaving a decode too wide to
    be worth emitting.  A refusal raises :class:`ValueError` naming which
    bound it hit; see the two constants for the measured curves and
    ``docs/walls.md`` for the argument.
    """
    n = _validate_truth_table(truth_table)
    result = _wii2d_routes(n, truth_table)
    if result is None:
        # Report the width the guard actually charged, not ``2 ** (n - 1)``:
        # for a table whose chain collapsed, that would name a width this
        # table never reached.  The two bounds refuse for different reasons
        # and say so separately, so a refusal never has to be guessed at.
        _chain, states = _wii2d_chain(n, truth_table)
        charged = _wii2d_cost(n, states)
        if charged > _WII2D_MAX_INDEX_DOMAIN:
            raise ValueError(
                f"the WII2D decode for this n == {n} table spans {charged} "
                f"points, past the _WII2D_MAX_INDEX_DOMAIN = "
                f"{_WII2D_MAX_INDEX_DOMAIN} cost guard; below the bound this "
                "is a size/time policy, but raising the constant does not "
                "buy the next doubling -- a domain-512 decode ratchets (live "
                "512 -> 475 over 19 steps, bit length doubling every step) "
                "and refuses on _WII2D_MAX_MAGNITUDE anyway.  See "
                "docs/walls.md: dense n == 10 is a wall of the exactly-once "
                "embed convention"
            )
        real = _wii2d_real_domain(states)
        if real > _WII2D_MAX_REAL_DOMAIN:
            raise ValueError(
                f"the WII2D chain for this n == {n} table leaves a decode "
                f"domain of {real} points, past the _WII2D_MAX_REAL_DOMAIN = "
                f"{_WII2D_MAX_REAL_DOMAIN} width guard; the table is inside "
                "the arity-scale cost guard but its chain found no merge, so "
                "the decode would be too wide to be worth emitting (see "
                "docs/walls.md)"
            )
        raise ValueError(
            "the WII2D n-embedding construction found no route: a branch "
            "decode ratcheted past _WII2D_MAX_MAGNITUDE or ran out of legal "
            "folds; at the domains the guards admit this is the rare "
            "doubling-trap pattern (about 1 in 10 sampled at domain 256), "
            "refused promptly rather than left to diverge"
        )
    start, routes = result
    flat = "\n".join(_wii2d_layout(n, start, routes, None))
    if width is None or max(len(line) for line in flat.split("\n")) <= width:
        return flat
    # Measured on the rendered text rather than on the grid's cell count: a
    # junction cell is a four-character ``{Xi}`` in the template, so the two
    # differ by more than the fold's own margin.
    return "\n".join(_wii2d_layout(n, start, routes, width))
