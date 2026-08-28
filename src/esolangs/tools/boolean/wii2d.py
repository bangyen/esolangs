"""Boolean-function generator for WII2D (parameterized convention).

WII2D is a no-input grid language, so this follows the parameterized
convention described in :mod:`esolangs.tools.boolean.parameterized`: the
template's ``{Xi}`` placeholders are junction cells the harness fills with
``>`` (bit 0) or ``v`` (bit 1), one program per input combination.

The branch op strings are *constructed*, not searched -- see
:func:`_wii2d_routes` for the two-part construction (an index chain and a
folding decode) and :func:`_wii2d_decode` for the fold algebra it rests on.
"""

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
# -- ``^v<>`` are static cells the harness fills, so no cell's behaviour can
# depend on the accumulator -- which means a junction's two op strings are
# shared by every prefix that reaches it.  That pins the construction down to
# one shape: the chain can only accumulate the bits into a single number, and
# a final op string has to turn that number into the table entry.
# :func:`_wii2d_routes` does exactly that, in two constructed halves.

# The op alphabet the construction draws on: digits set the accumulator,
# ``+ - * / s`` are arithmetic (increment, decrement, double, halve, square),
# and a space is a no-op.  Only ``s`` is not order-preserving, which is why
# the decode below is built out of folds around it.

# How many fold candidates :func:`_wii2d_decode` keeps at each step, and the
# widths it escalates through when a narrower one dead-ends.
#
# The fold choice is not always safe to make greedily: the locally-largest
# merge can leave a state whose remaining values no later fold can separate,
# so a width of one dead-ends on a small fraction of patterns.  Widening
# fixes those, and the cost of a wider pass is small enough to just pay it on
# the patterns that need it -- 4 settles the great majority, and every
# pattern tested exhaustively through ``D == 16`` (the widest domain the
# generator asks for, at ``n == 5``) is decoded by 32 or less.
#
# Escalating rather than always running at the widest width keeps the common
# case cheap without making the answer depend on anything but the table: the
# ladder is fixed, so the width a pattern lands on is a property of the
# pattern.
_WII2D_BEAMS: tuple[int, ...] = (4, 16, 32)

# Fold centres whose square would exceed this are rejected.  Op-string length
# is grid width -- ``'-' * c`` is c cells -- so an unbounded fold centre is a
# program too wide to be worth emitting even when it is correct.
_WII2D_FOLD_CAP = 10**9


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


def _wii2d_compress(
    values: list[int], bits: list[int], ops: str
) -> tuple[list[int], str]:
    """Shrink the live values with ``/``, steering with ``+`` when needed.

    Halving is the only thing keeping the fold centres small: ``s`` squares,
    so without compression the centres (and the ``'-' * c`` runs that spell
    them) grow past any width worth emitting.  A plain halving sometimes
    collides two values that need different bits; incrementing first pairs
    neighbours the other way round, which usually clears the collision.
    """
    while max(abs(v) for v in values) > 1:
        for shift in (0, 1):
            candidate = [(v + shift) // 2 for v in values]
            if _wii2d_points(candidate, bits) is None:
                continue
            if set(candidate) == set(values):
                continue  # no progress; a further halving would not help
            ops += "+" * shift + "/"
            values = candidate
            break
        else:
            return values, ops
    return values, ops


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
    # after the subtraction the values are ``low - high`` and 0, so the
    # halving run only has to be long enough to bottom that span out at -1.
    runs = max(abs(low - high).bit_length() + 1, 1)
    indicator = _wii2d_offset(high) + "/" * runs + "+"
    if live[low] == 0 and live[high] == 1:
        return indicator
    return indicator + "-s"


def _wii2d_folds(
    values: list[int], bits: list[int]
) -> list[tuple[int, int, str, list[int]]]:
    """Return the candidate folds from this state, best first.

    ``s`` is the only op that is not order-preserving, and ``'-' * c + 's'``
    sends ``x`` to ``(x - c) ** 2``, which merges exactly the pairs
    equidistant from ``c``.  That is the whole trick: it is the one way to
    make two different accumulator values agree without a conditional, so
    every fold is one step toward the two values a threshold can read.  A
    fold is legal only when every pair it merges needs the same bit.
    Doubling first (``*``) makes every gap even, which opens the midpoints
    that are otherwise half-integral.
    """
    out: list[tuple[int, int, str, list[int]]] = []
    for scale in (0, 1):
        scaled = [v * 2 for v in values] if scale else list(values)
        live = _wii2d_points(scaled, bits)
        if live is None:
            continue
        points = sorted(live)
        centres = {
            (points[i] + points[j]) // 2
            for i in range(len(points))
            for j in range(i + 1, len(points))
            if (points[i] + points[j]) % 2 == 0
        }
        for centre in centres:
            merged: dict[int, int] = {}
            for value in points:
                folded = (value - centre) ** 2
                if folded > _WII2D_FOLD_CAP:
                    break
                if merged.get(folded, live[value]) != live[value]:
                    break
                merged[folded] = live[value]
            else:
                if len(merged) >= len(points):
                    continue  # nothing merged; the fold buys no progress
                fragment = ("*" if scale else "") + _wii2d_offset(centre) + "s"
                folded_values = [(v - centre) ** 2 for v in scaled]
                folded_values, fragment = _wii2d_compress(folded_values, bits, fragment)
                out.append(
                    (len(set(folded_values)), len(fragment), fragment, folded_values)
                )
    out.sort(key=lambda cand: (cand[0], cand[1]))
    return out


def _wii2d_decode_at(pattern: list[int], beam: int) -> str | None:
    """Construct the decode at one fold width; see :func:`_wii2d_decode`."""
    bits = list(pattern)
    values, ops = _wii2d_compress(list(range(len(bits))), bits, "")
    states = [(values, ops)]
    for _ in range(4 * len(bits) + 8):
        nxt: list[tuple[list[int], str]] = []
        for state_values, state_ops in states:
            live = _wii2d_points(state_values, bits)
            if live is None:
                continue
            if len(live) <= 2:
                return state_ops + _wii2d_threshold(live)
            for _size, _cost, fragment, folded in _wii2d_folds(state_values, bits)[
                :beam
            ]:
                nxt.append((folded, state_ops + fragment))
        if not nxt:
            return None
        nxt.sort(key=lambda state: (len(set(state[0])), len(state[1])))
        states = nxt[:beam]
    for state_values, state_ops in states:
        live = _wii2d_points(state_values, bits)
        if live is not None and len(live) <= 2:
            return state_ops + _wii2d_threshold(live)
    return None


def _wii2d_decode(pattern: list[int]) -> str | None:
    """Construct an op string realizing ``pattern`` on ``0 .. len(pattern)-1``.

    This is the one primitive the generator needs: every route is either a
    fixed chain step or a call to this.  It folds the live values together
    (:func:`_wii2d_folds`) until two remain, then reads those two out with a
    threshold (:func:`_wii2d_threshold`), widening through
    :data:`_WII2D_BEAMS` if a narrower fold width dead-ends.

    Returns ``None`` if even the widest width dead-ends.  No pattern tested
    through ``D == 16`` -- the widest domain the generator asks for -- does.
    """
    bits = list(pattern)
    if all(bit == bits[0] for bit in bits):
        return str(bits[0])  # constant: a digit is the whole decode
    for beam in _WII2D_BEAMS:
        ops = _wii2d_decode_at(bits, beam)
        if ops is not None:
            return ops
    return None


def _wii2d_routes(n: int, table: str) -> tuple[int, list[tuple[str, str]]] | None:
    """Construct the per-junction branch op strings realizing ``table``.

    A junction chain of length ``n`` (one per input) computes

        acc = R[n-1][b_n-1] ( ... R[0][b_0] ( start ) ... )

    for each input combo, where each ``R[i][b]`` is an op string applied when
    input ``i`` takes value ``b``.  Since no op string can depend on the bits
    already read, the construction splits the work in two:

    * **Index chain.**  Junctions 0 through ``n - 2`` use ``('*', '*+')``, so
      each one doubles the accumulator and adds the bit.  After them the
      accumulator is exactly ``q``, the integer whose bits are the first
      ``n - 1`` inputs -- Horner's rule, and the only thing a prefix-blind
      chain can accumulate.
    * **Decode.**  The last junction's two branches are the two columns of
      the table read at ``q``: branch ``b`` must map ``q`` to
      ``table[2 * q + b]``.  Each is an arbitrary 0/1 pattern on
      ``0 .. 2 ** (n - 1)``, which :func:`_wii2d_decode` constructs.

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
    half = 2 ** (n - 1)
    branch0 = _wii2d_decode([int(table[2 * q]) for q in range(half)])
    branch1 = _wii2d_decode([int(table[2 * q + 1]) for q in range(half)])
    if branch0 is None or branch1 is None:
        return None
    return 0, [("*", "*+")] * (n - 1) + [(branch0, branch1)]


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


def _wii2d_layout(n: int, start: int, routes: list[tuple[str, str]]) -> list[str]:
    """Lay out the junction chain template.

    ``{Xi}`` placeholders on row 0, each branch's op cells on row 0 (bit 0)
    or on a dedicated detour row below (bit 1), re-merging before the next
    junction.  Nothing is spaced apart: a merge sits directly on the column
    past the longer branch, the next junction directly past the merge, and
    the decode directly past the last merge.  The layout used to leave one
    blank column of separation at each of those seams, but a blank column
    carries only straight eastward travel -- the pointer crosses it and
    arrives at the same cell either way -- so it bought legibility in the
    template at the cost of width in every emitted program.
    """
    # A junction is a single cell: the fill writes 'v' to take the 1-branch
    # or '>' to continue east, and nothing on row 0 ever occupies the column
    # after it.  The '{Xi}' spelling is four characters only because that is
    # how the placeholder is written, and instantiation gives the rest back.
    placeholder_width = 1

    placeholder_col = [0] * n
    # column 0 is always '>'; when there's a start digit (the construction only
    # ever returns a single digit 0-9), it sits at column 1 and the first
    # placeholder follows it at column 2.  With no digit the placeholder
    # starts right after the '>'.  (No table found at n <= 3 needs a nonzero
    # start, so this is the untravelled branch -- but the digit's column is
    # its own, not the junction's.)
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
    ascii_zero = _ASCII_ZERO
    total_cols = decode_start + ascii_zero + len("~.")

    grid = [[" "] * total_cols for _ in range(n + 1)]
    grid[0][0] = ">"
    if start:
        grid[0][1] = str(start)
    for i in range(n):
        # The junction's one cell, spelled out once the layout is finished:
        # the placeholder's four characters are how it is written, not how
        # much room the junction needs, and the fill gives the difference
        # back.
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
    # shift the 0/1 accumulator up to the ASCII digit and print it
    for k in range(ascii_zero):
        grid[0][decode_start + k] = "+"
    grid[0][decode_start + ascii_zero] = "~"
    grid[0][decode_start + ascii_zero + 1] = "."
    grid[1][0] = "!"
    rows = ["".join(row).rstrip() for row in grid]
    return [
        re.sub("\x00(\\d+)\x00", lambda m: "{X" + m.group(1) + "}", row) for row in rows
    ]


def wii2d(truth_table: str) -> str:
    """Build a WII2D template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

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
    """
    n = _validate_truth_table(truth_table)
    result = _wii2d_routes(n, truth_table)
    if result is None:
        raise ValueError(
            "the WII2D n-embedding construction found no route: the decode "
            "folds dead-ended on this table"
        )
    start, routes = result
    return "\n".join(_wii2d_layout(n, start, routes))
