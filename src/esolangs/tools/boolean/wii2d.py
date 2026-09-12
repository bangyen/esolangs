r"""Boolean-function generator for WII2D (parameterized convention)."""

import heapq
import re

from esolangs.exceptions import GeneratorCapError
from esolangs.tools.boolean.helpers import _ASCII_ZERO, _validate_truth_table

__all__ = ["wii2d"]


# --- WII2D (no-input grid.
# .
# WII2D's only I/O is the ``~``.
# boolean generator follows the.
# ``{Xi}`` placeholders are.
# program per input combination.
# 0, the pointer continues.
# .
# A full decision tree would.
# level (2**n - 1 junctions),.
# once, but WII2D has no memory.
# way the tape/register.
# do.
# junctions form a *merging.
# accumulator and the branches.
# input is embedded exactly.
# table entry.
# .
# Nothing here searches.
# -- ``^v<>`` are static cells.
# strings are shared by every.
# construction down to one.
# a single number, and a final.
# table entry.
# halves.
# .
# The chain accumulates the.
# index.
# accumulator value, and.
# them: merging keeps the.
# decode a narrower domain than.
# ``('*', '*+')`` is the last.
# the walk total -- see.

# The op alphabet the.
# ``+ - * / s`` are arithmetic.
# and a space is a no-op.
# the decode below is built out.

# The fold rule is.
# the single best candidate.
# ranking (smallest magnitude,.
# string).
# candidate is taken at each.
# choices produces.
# .
# The fold only *reshapes*;.
# steering an add-then-halve.
# what carries the wide.
# sampled patterns where the.
# .
# That this suffices is not an.
# pattern through ``D == 16``,.
# verified by applying the.
# ``docs/generators/wii2d_genera.

# The widest fold centre worth.
# ``'-' * c`` is spelled out in.
# width, not on the arithmetic:.
# utterly useless, since the.
# .
# Compression normally keeps.
# come out of it), and this.
# has drifted somewhere it.
# nothing: the ranking promotes.
# ``D == 16`` still decodes.
# :func:`_wii2d_folds`) means.
# already avoiding.
_WII2D_MAX_CENTRE = 4096

# The largest live-value.
# as diverging.
# every table that builds, the.
# live values small -- max 1922.
# eight sampled domain-256.
# roughly doubling its bit.
# climbed 14 -> 670597 bits.
# past this bound never comes.
# success.
# .
# **This bound is.
# centre cap would reach.
# patterns do not stop at all.
# 0.45-1.59s ran 136s, 183s and.
# 299526, 1173459 and 644663.
# 256 guard would ship hangs,.
# than a property of the sample.
# candidates, so it cannot.
# and it is deterministic where.
# depend on the machine.
_WII2D_MAX_MAGNITUDE = 1 << 20

# How many candidate folds are.
# .
# Compression is the expensive.
# over every close pair -- and.
# compressing every candidate.
# .
# The screen cannot be a.
# uncompressed magnitude says.
# early exit justified that way.
# approximation: the shortlist.
# its members get the real key.
# .
# Eight, raised from four when.
# are measured together: the.
# 286669 characters over the.
# 285903 the one-level walk.
# turns it into a win at 261019.
# compressed magnitude much.
# the screen has to keep more.
_WII2D_SHORTLIST = 8

# How many legal shifts a.
# set is exact (the arc-union.
# members are scored for.
# so the smallest legal shift.
# approximation with the same.
_WII2D_SHIFT_SAMPLES = 40

# The widest decode domain the.
# that path is used up to ``n.
# .
# **This is a cost policy, not.
# against :func:`_wii2d_cost`.
# domain the chain actually.
# alone.
# arity: an ``n == 8``.
# builds in 217 characters,.
# without ever looking at it.
# .
# What the constant buys is.
# doubles.
# points via the popcount chain.
# measured.
# width and time tables this.
# .
# 256 admits dense ``n == 9``.
# (sha256-derived, see the grid.
# with all 512 rows executed.
# *returns* -- an aborted.
# prompt rather than a hang,.
# :data:`_WII2D_MAX_MAGNITUDE`.
# a sample.
# refusal curves.
# .
# Dense ``n == 10`` (domain.
# is 256.
# branch: with the magnitude.
# count crawling 512 -> 475.
# step, 9 -> 1089888 bits, the.
# better -- 512 -> 373 over 19.
# is a wall of the fold algebra.
# a budget choice -- see.
_WII2D_MAX_INDEX_DOMAIN = 256

# The widest *real* chain.
# arity-scale guard above.
# .
# These two bound different.
# the *minimum* of the worst.
# collapses is judged on what.
# a table can be admitted on.
# with no merge available the.
# pair can leave a domain far.
# .
# Measured, that overshoot is.
# as :data:`_WII2D_MAX_CENTRE`.
# emitting.
# one that does not.
# refusing the latter is not a.
_WII2D_MAX_REAL_DOMAIN = 256


def _wii2d_apply(ops: str, value: int) -> int:
    r"""Apply a WII2D op string to an accumulator value (the op cell order)."""
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
    r"""Return the op string subtracting ``c`` (``'-'`` or ``'+'``."""
    return "-" * c if c >= 0 else "+" * (-c)


def _wii2d_points(values: list[int], bits: list[int]) -> dict[int, int] | None:
    r"""Map each live accumulator value to its required bit."""
    seen: dict[int, int] = {}
    for value, bit in zip(values, bits, strict=True):
        if seen.get(value, bit) != bit:
            return None
        seen[value] = bit
    return seen


def _wii2d_legal_shifts(arcs: list[tuple[int, int]], block: int) -> list[int]:
    r"""Return up to :data:`_WII2D_SHIFT_SAMPLES` legal shifts, ascending."""
    if not arcs:
        return list(range(min(_WII2D_SHIFT_SAMPLES, block)))
    flat = []
    for start, length in arcs:
        end = start + length
        if end <= block:
            flat.append((start, end))
        else:  # pragma: no cover - Horner is legal at every level
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
    r"""Merge and shrink the live values with add-then-halve runs."""
    while True:
        live = _wii2d_points(values, bits)
        if live is None:  # pragma: no cover - callers pass legal states
            return values, ops
        points = sorted(live)
        span = points[-1] - points[0]
        # ``max(abs(v)) <= 1`` is the.
        # small span at a large.
        # strictly lowers the maximum.
        # span alone would hand the.
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
    r"""Return the op string collapsing one or two live values to their."""
    points = sorted(live)
    if len(points) == 1:
        return str(live[points[0]])
    low, high = points
    if live[low] == live[high]:
        # Two values, one answer: a.
        # compression stops at ``{0,.
        # below would answer (0, 1) or.
        return str(live[low])
    # after the subtraction the.
    # halving run only has to be.
    runs = max(abs(low - high).bit_length() + 1, 1)
    indicator = _wii2d_offset(high) + "/" * runs + "+"
    if live[low] == 0 and live[high] == 1:
        return indicator
    return indicator + "-s"


def _wii2d_folds(
    values: list[int], bits: list[int]
) -> list[tuple[int, int, int, str, list[int]]]:
    r"""Return the candidate folds from this state, best first."""
    # Enumerate the legal folds.
    # than by centre.
    # symmetric about ``c``, so a.
    # ``2c`` needs two different.
    # less the number of pairs.
    # one ``abs(p - c)``, so those.
    # off once therefore replaces.
    # dropping the step from ``O(P.
    # 6.3s dense ``n == 9`` build.
    # unchanged: a centre whose.
    # one the rescan rejected, so.
    # pair.
    # .
    # Compression stays the.
    # domain, each step rebuilding.
    # takes the head, so only the.
    # members' folded values are.
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
        # ``2c`` for every pair that.
        crossing: set[int] = set()
        for point in zeros:
            crossing.update([point + other for other in ones])
        # ``2c -> how many same-bit.
        merging: dict[int, int] = {}
        for group in (zeros, ones):
            for index, point in enumerate(group):
                for double in [point + other for other in group[index + 1 :]]:
                    merging[double] = merging.get(double, 0) + 1
        # sorted, not raw dict order:.
        # the order candidates were.
        # the emitted program depend on.
        for double in sorted(merging):
            if double % 2 or double in crossing:
                continue
            centre = double >> 1
            if abs(centre) > _WII2D_MAX_CENTRE:
                continue  # correct but too wide to spell.
            # The shortlist key, on the.
            # *screen*, not the ranking:.
            # an order of magnitude (529 to.
            # predict the true order and is.
            # monotone in the distance from.
            # value is always one of the.
            pending.append(
                (
                    (
                        max((span_low - centre) ** 2, (span_high - centre) ** 2),
                        len(points) - merging[double],
                        scale + abs(centre) + 1,
                    ),
                    len(pending),  # stable-sort tie-break, made.
                    scale,
                    centre,
                )
            )

    # Compress only the shortlist,.
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
    # Magnitude first.
    # live values *are* the.
    # keeps the emitted grid small.
    # the same two-value state.
    # characters against 285903.
    # -- which holds against the.
    # against the one-level halving.
    out.sort(key=lambda cand: (cand[1], cand[0], cand[2]))
    return out


def _wii2d_decode(pattern: list[int]) -> str | None:
    r"""Construct an op string realizing ``pattern`` on ``0 ."""
    bits = list(pattern)
    if all(bit == bits[0] for bit in bits):
        return str(bits[0])  # constant: a digit is the.
    values, ops = _wii2d_compress(list(range(len(bits))), bits, "")
    # A fold strictly reduces the.
    # than there are values to.
    for _ in range(len(bits) + 1):
        live = _wii2d_points(values, bits)
        if live is None:
            return None
        # The ratchet abort: a state.
        # so give up rather than let.
        # See.
        # sits ahead of the two-live.
        # spelling is bounded too, not.
        if max(abs(v) for v in values) > _WII2D_MAX_MAGNITUDE:
            return None
        if len(live) <= 2:
            return ops + _wii2d_threshold(live)
        candidates = _wii2d_folds(values, bits)
        if not candidates:
            return None
        # _wii2d_folds returns.
        # so taking the head is the.
        *_rank, fragment, folded = candidates[0]
        values, ops = folded, ops + fragment
    return None


# The op-string pairs the chain.
# the arithmetic offsets, then.
# ones, with Horner last.
# .
# The order is *semantic*, not.
# holds 42 total-character.
# one character sitting behind.
# reproduces it -- a sweep of.
# lengths, per-character.
# lexicographic compositions,.
# shipped sequence, against a.
# deliberately sorted list.
# than a failed search: index.
# length, so no key monotone in.
# .
# What the order buys is size,.
# permuting the merge entries.
# emitted programs with zero.
# random permutations on total.
# measured preference over a.
# costs characters, never.
# .
# A chain junction is a pair.
# when the input is 0, ``B``.
# reaching that junction --.
# flow, so a junction cannot.
# constraint the whole.
# .
# Horner ``('*', '*+')`` sits.
# every level unconditionally.
# cofactors never share an.
# but would be.
# ``2w + 1``, which differ in.
# which the invariant already.
# there is always at least one.
# .
# The earlier entries are the.
# same residual function they.
# set small and handing the.
# in a fixed order and the.
# pass with no backtracking and.
# .
# That order is semantic, not.
# still sits after three.
# characters -- with or without.
# reproduces none of it.
# which is correct, so.
# permuting the twenty merge.
# emitted programs with zero.
# random permutations on total.
# that tuning, not just.
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
    r"""Read one input bit with ``ops``, or ``None`` if that pair is."""
    low, high = ops
    out: list[tuple[str, int]] = []
    for cofactor, value in states:
        half = len(cofactor) // 2
        out.append((cofactor[:half], _wii2d_apply(low, value)))
        out.append((cofactor[half:], _wii2d_apply(high, value)))
    out = list(dict.fromkeys(out))  # identical (cofactor, value).
    seen: dict[int, str] = {}
    for cofactor, value in out:
        if value < 0:
            # The decode indexes its.
            # negative has no slot.
            # keeps the chain's values in.
            # :func:`_wii2d_columns` be.
            return None
        if seen.setdefault(value, cofactor) != cofactor:
            return None
    return out


def _wii2d_chain(
    n: int, table: str
) -> tuple[list[tuple[str, str]], list[tuple[str, int]]]:
    r"""Build the first ``n - 1`` junctions and the states they leave."""
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
    r"""Return the last junction's two columns as patterns over the values."""
    width = max(value for _, value in states) + 1
    # Values are non-negative --.
    # would make one -- so every.
    # zero they are filled with: no.
    # is a don't-care the decode.
    # little size and no.
    low = [0] * width
    high = [0] * width
    for cofactor, value in states:
        low[value] = int(cofactor[0])
        high[value] = int(cofactor[1])
    return low, high


def _wii2d_real_domain(states: list[tuple[str, int]]) -> int:
    r"""Return the decode domain the chain walk actually left."""
    return max(value for _cofactor, value in states) + 1


def _wii2d_cost(n: int, states: list[tuple[str, int]]) -> int:
    r"""Return the decode width :data:`_WII2D_MAX_INDEX_DOMAIN` is charged."""
    worst_case: int = 2 ** (n - 1)
    return min(worst_case, _wii2d_real_domain(states))


def _wii2d_routes(n: int, table: str) -> tuple[int, list[tuple[str, str]]] | None:
    r"""Construct the per-junction branch op strings realizing ``table``."""
    if n == 2:
        return 0, _wii2d_n2_closed_form(table)
    popcount_map = _wii2d_symmetric_popcount_map(n, table)
    if popcount_map is not None:
        parity_result = _wii2d_parity_routes(n, popcount_map)
        if parity_result is not None:
            return parity_result
        # branch b of the last junction.
        # bits and must answer for a.
        low = _wii2d_decode(popcount_map[:n])
        high = _wii2d_decode(popcount_map[1:])
        if low is not None and high is not None:
            return 0, [("", "+")] * (n - 1) + [(low, high)]
    # Walk the chain *before* the.
    # fixed catalogue scan per.
    # actually leaves costs nothing.
    chain, states = _wii2d_chain(n, table)
    # Refused on cost, not on.
    # either width.
    # the constants for what each.
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


# For n == 2 a closed form.
# bit) or 0 (a one bit), and.
# the table's two columns from.
# column pattern maps to a.
# ``+``, 1 then 0 -> ``s``.
_WII2D_N2_DECODE = {(0, 0): "0", (0, 1): "+", (1, 0): "s", (1, 1): "1"}


def _wii2d_n2_closed_form(table: str) -> list[tuple[str, str]]:
    r"""Return the two-junction routes for a 2-input table, closed form."""
    t = [int(c) for c in table]
    return [
        ("-", "*"),
        (
            _WII2D_N2_DECODE[(t[0], t[2])],  # column for a zero last bit.
            _WII2D_N2_DECODE[(t[1], t[3])],  # column for a one last bit.
        ),
    ]


def _wii2d_symmetric_popcount_map(n: int, table: str) -> list[int] | None:
    r"""Return ``table`` as a function of popcount, or ``None`` if not."""
    result: list[int | None] = [None] * (n + 1)
    for combo in range(2**n):
        p = bin(combo).count("1")
        v = int(table[combo])
        if result[p] is None:
            result[p] = v
        elif result[p] != v:
            return None
    return [v for v in result if v is not None]  # every p in 0..n is reachable.


def _wii2d_parity_routes(
    n: int, popcount_map: list[int]
) -> tuple[int, list[tuple[str, str]]] | None:
    r"""Return the exact chain for parity or its complement, else ``None``."""
    if popcount_map == [p % 2 for p in range(n + 1)]:
        first = ("", "+")
    elif popcount_map == [1 - p % 2 for p in range(n + 1)]:
        first = ("+", "")
    else:
        return None
    routes = [first] + [("", "-s")] * (n - 1)
    return 0, routes


# The narrowest fold that makes.
# op column between them.
# refused, matching the width.
_WII2D_MIN_FOLD_SPAN = 3


def _wii2d_fold_decode(
    decode_start: int, ops: str, span: int, first_row: int
) -> dict[tuple[int, int], str]:
    r"""Lay ``ops`` out as a boustrophedon below the chain, not along row 0."""
    cells: dict[tuple[int, int], str] = {}
    row = first_row
    # The entry turn sits at the.
    # or east of the span, so it.
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
    r"""Lay out the junction chain template."""
    # A junction is a single cell:.
    # or '>' to continue east, and.
    # it.
    # the placeholder is written,.
    placeholder_width = 1

    placeholder_col = [0] * n
    # column 0 is always '>'; a.
    # returns a single digit 0-9).
    # at column 2.
    # (No table found at n <= 3.
    # untravelled branch -- but the.
    # junction's.).
    placeholder_col[0] = 2 if start != 0 else 1
    merge_col = [0] * n
    for i in range(n):
        r0, r1 = routes[i]
        # row 0 runs placeholder, then.
        # placeholder_width + len(r0);.
        # placeholder_col[i] + 1 +.
        # column past whichever row.
        # the first column past the.
        row0_end = placeholder_width + len(r0)
        row1_end = 1 + len(r1)
        merge_col[i] = placeholder_col[i] + max(row0_end, row1_end)
        if i + 1 < n:
            placeholder_col[i + 1] = merge_col[i] + 1

    decode_start = merge_col[n - 1] + 1  # the column past the last.
    shift_to_ascii_digit = _ASCII_ZERO
    print_op = "~."
    flat_cols = decode_start + shift_to_ascii_digit + len(print_op)

    # The chain cannot fold -- each.
    # and each detour row hangs.
    # program this builds is the.
    # on.
    # .
    # Whether to fold at all is.
    # ``flat_cols`` counts grid.
    # in characters -- and a.
    # which is four characters wide.
    # requested width against the.
    # rendered well past it: parity.
    # characters, so a request for.
    # measures the rendered flat.
    # too wide, so this folds.
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
        # The junction's one cell,.
        # the placeholder's four.
        # room the junction needs, and.
        grid[0][placeholder_col[i]] = "\x00" + str(i) + "\x00"
        r0, r1 = routes[i]
        for k, ch in enumerate(r0):
            grid[0][placeholder_col[i] + placeholder_width + k] = ch
        # 1-branch: descend to row i+1,.
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
    r"""Build a WII2D template for the given truth table."""
    n = _validate_truth_table(truth_table)
    result = _wii2d_routes(n, truth_table)
    if result is None:
        # Report the width the guard.
        # for a table whose chain.
        # table never reached.
        # and say so separately, so a.
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
                "docs/walls.md: dense n == 10 is a wall of the exactly-once "
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
                "docs/walls.md)"
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
    # Measured on the rendered text.
    # junction cell is a.
    # differ by more than the.
    return "\n".join(_wii2d_layout(n, start, routes, width))
