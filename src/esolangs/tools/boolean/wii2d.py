"""Boolean-function generator for WII2D (parameterized convention).

WII2D is a no-input grid language, so this follows the parameterized
convention described in :mod:`esolangs.tools.boolean.parameterized`: the
template's ``{Xi}`` placeholders are junction cells the harness fills with
``>`` (bit 0) or ``v`` (bit 1), one program per input combination.

The bulk of this module is the *chain search* that finds the branch op
strings letting each input be embedded exactly once -- see
:func:`_wii2d_search` for the counting-bound argument that bounds which
tables the search can reach.
"""

import re
from collections.abc import Callable

from esolangs.tools.boolean.helpers import _validate_truth_table

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
# table entry.  WII2D's ops are not monotone (``s`` sends -1 to 1), so the
# decoding routes can distinguish any table -- every table through four
# inputs (exhaustively at one through three, sampled dense at four) and
# sampled dense five-input tables are reachable (verified against the
# interpreter), and symmetric tables of any arity are covered by closed
# forms.  The route op sequences are searched per table; the search raises
# :class:`ValueError` when it cannot fit a table in its budget (large dense
# non-symmetric tables past ``n == 5``).

# The op alphabet the search composes per junction branch: digits set the
# accumulator, ``+ - * / s`` are arithmetic, and a space is a no-op.
_WII2D_OPS = ["+", "-", "*", "/", "s"] + [str(d) for d in range(10)]


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


def _wii2d_search(n: int, table: str) -> tuple[int, list[tuple[str, str]]] | None:
    """Search for the per-junction branch op sequences realizing ``table``.

    A junction chain of length ``n`` (one per input) computes

        acc = R[n-1][b_n-1] ( ... R[0][b_0] ( start ) ... )

    for each input combo, where each ``R[i][b]`` is an op string applied when
    input ``i`` takes value ``b``.  The search finds the ``2n`` op strings and
    a starting accumulator value such that the composition equals the table
    entry for every combo.  It works backward from the last junction (the
    most constrained: its two branches must map the up to 2**(n-1) incoming
    values to the table's two columns), propagating the set of acceptable
    values for each prefix; returns ``(start, routes)`` or ``None`` if the
    budget runs out.

    ``n == 2`` uses a closed form (:func:`_wii2d_n2_closed_form`) instead of
    searching.  Parity and its complement (symmetric tables where the entry
    is the popcount's low bit) get an exact O(1) closed form
    (:func:`_wii2d_parity_routes`) up front: the general search below *can*
    reach parity at maxlen == 2 for every arity tested (up to n == 20), but
    its cost still grows with n (0.01s at n == 12, ~2s at n == 20), so the
    closed form is a speed win, not a reachability one.  Every other
    symmetric table (AND/OR/majority/threshold-k of any arity) is left to the
    general search first, because it is usually faster there too (its
    preimage-effect pruning makes monotone tables cheap); only if every
    length in the general ladder fails does :func:`_wii2d_symmetric_search`
    get a turn, reducing a symmetric table to a popcount accumulator plus a
    length-``n`` decode lookup instead of the full ``2**n``-row table.  That
    reduction is not just a speed trick: no chain with op strings bounded by
    a fixed length L can represent every table once n is large enough.  There
    are at most ``10 * 15 ** (2*n*(L+1))`` distinct chains (2n routes times
    (L+1) choices of alphabet-15 op per cell, times 10 start values) against
    ``2 ** (2**n)`` tables, so universality needs ``L >~ 2**n / (7.8*n)`` --
    vacuous at small n, but it forces L >= 12 at n == 10 and L >= 43 at
    n == 12, both well past the length-6 ladder below.  So the general search
    is *guaranteed* to eventually fail on some tables at high arity
    (majority/threshold-k among them) regardless of how it is tuned, which is
    where the popcount reduction earns its keep.

    For non-symmetric tables, larger ``n`` tries the op strings at length 2
    through 6 with an increasing per-length budget; length 2 suffices for
    every table through three inputs, length 3 for sampled dense tables at
    four, and length 5-6 for sampled tables at five.  The requirement sets
    and preimages are bit-vectors (one bit per reachable accumulator value),
    and routes that share a preimage effect are deduplicated, so the search
    stays tractable at the longer lengths.
    """
    import time

    if n == 2:
        return 0, _wii2d_n2_closed_form(table)
    popcount_map = _wii2d_symmetric_popcount_map(n, table)
    if popcount_map is not None:
        parity_result = _wii2d_parity_routes(n, popcount_map)
        if parity_result is not None:
            return parity_result
    t = [int(c) for c in table]

    # Longer op strings cover denser tables (every table through n == 4 at
    # length 3, sampled n == 5 at length 5-6); the budgets grow accordingly.
    for maxlen, budget in ((2, 4.0), (3, 8.0), (4, 12.0), (5, 30.0), (6, 60.0)):
        domain = _wii2d_domain(maxlen, cap=10**6)
        index = {v: i for i, v in enumerate(domain)}
        seqs = _wii2d_sequences(maxlen, domain)
        inv = []
        for s in seqs:
            m: dict[int, int] = {}
            for v in domain:
                y = _wii2d_apply(s, v)
                m[y] = m.get(y, 0) | (1 << index[v])
            inv.append(m)

        def pre(
            sidx: int,
            targets: int,
            inv: list[dict[int, int]] = inv,
            domain: list[int] = domain,
        ) -> int:
            out = 0
            m = inv[sidx]
            bits = targets
            while bits:
                low = bits & -bits
                out |= m.get(domain[low.bit_length() - 1], 0)
                bits ^= low
            return out

        deadline = time.monotonic() + budget
        result = _wii2d_search_start(n, t, seqs, pre, index, deadline)
        if result is not None:
            return result
    if popcount_map is not None:
        return _wii2d_symmetric_search(n, popcount_map)
    return None


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


def _wii2d_symmetric_search(
    n: int, popcount_map: list[int]
) -> tuple[int, list[tuple[str, str]]] | None:
    """Reduce a symmetric table to a popcount accumulator plus a small decode.

    The first ``n - 1`` junctions all use ``('', '+')``, so the accumulator
    equals the popcount of the first ``n - 1`` bits (0 through ``n - 1``)
    regardless of the table.  The last junction only has to turn that
    popcount into the table entry, so its two branches are searched over a
    domain of size ``n`` instead of the full ``2**n`` rows the general search
    fits -- a much cheaper problem that stays tractable well past where the
    general chain search starts to struggle, though it can still fail (e.g.
    non-monotone symmetric tables like "exactly k of n ones" for large ``n``)
    since a single op string cannot express every popcount -> bit map.
    """
    import time

    domain_size = n  # popcount before the last bit ranges over 0..n-1
    deadline = time.monotonic() + 8.0
    for maxlen in range(0, 7):
        if time.monotonic() > deadline:
            return None
        dom = _wii2d_domain(maxlen, cap=10**6)
        if not all(p in dom for p in range(domain_size)):
            continue  # op strings this short can't even reach every popcount
        seqs = _wii2d_sequences(maxlen, dom)
        last0 = next(
            (
                s
                for s in seqs
                if all(
                    _wii2d_apply(s, p) == popcount_map[p] for p in range(domain_size)
                )
            ),
            None,
        )
        last1 = next(
            (
                s
                for s in seqs
                if all(
                    _wii2d_apply(s, p) == popcount_map[p + 1]
                    for p in range(domain_size)
                )
            ),
            None,
        )
        if last0 is not None and last1 is not None:
            routes = [("", "+")] * (n - 1) + [(last0, last1)]
            return 0, routes
    return None


def _wii2d_search_start(
    n: int,
    t: list[int],
    seqs: list[str],
    pre: Callable[[int, int], int],
    index: dict[int, int],
    deadline: float,
) -> tuple[int, list[tuple[str, str]]] | None:
    """Search the junction routes, returning ``(start, routes)``.

    The requirement sets are bit-vectors over the domain; ``pre`` maps a
    requirement bit-vector to the bit-vector of incoming values a route can
    produce it from.  The whole search tree (the route pairs tried at every
    junction) is independent of the starting accumulator value -- ``start``
    only decides whether a complete chain is accepted at the leaf -- so the
    chain is searched once and the leaf's requirement set yields every start
    value the chain works for.  A junction's sub-search depends only on its
    requirement set, so results are memoized by ``(junction, requirement set)``
    to avoid re-solving the same sub-problem reached through different parents.
    """
    import time

    start_bits = 0
    for v in range(10):
        if v in index:
            start_bits |= 1 << index[v]
    memo: dict[
        tuple[int, tuple[int, ...]], tuple[list[tuple[str, str]], int] | None
    ] = {}
    reqsets = [[1 << index[t[c]] for c in range(2**n)]]

    def search(i: int) -> tuple[list[tuple[str, str]], int] | None:
        if time.monotonic() > deadline:
            raise TimeoutError
        cur = reqsets[0]  # 2**(i+1) requirements
        key = (i, tuple(cur))
        if key in memo:
            return memo[key]
        # Two routes are interchangeable at this junction when they share the
        # same preimage effect on every requirement (they allow exactly the
        # same incoming values), so deduplicate by that effect to collapse the
        # |seqs|**2 pair search -- dense n == 5 tables exhaust this way.
        eff0: dict[tuple[int, ...], str] = {}
        for si, s in enumerate(seqs):
            eff0.setdefault(tuple(pre(si, cur[2 * p]) for p in range(2**i)), s)
        eff1: dict[tuple[int, ...], str] = {}
        for si, s in enumerate(seqs):
            eff1.setdefault(tuple(pre(si, cur[2 * p + 1]) for p in range(2**i)), s)
        # Try the least-constraining effects first (largest coverage: the most
        # incoming values they accept), so a solution is reached after a handful
        # of sub-problems instead of hundreds of dead ends.
        e0 = sorted(eff0.items(), key=lambda kv: -sum(x.bit_count() for x in kv[0]))
        e1 = sorted(eff1.items(), key=lambda kv: -sum(x.bit_count() for x in kv[0]))
        m = 2**i
        for a, r0 in e0:
            for b, r1 in e1:
                nxt = [0] * m
                ok = True
                for p in range(m):
                    w = a[p] & b[p]
                    if not w:
                        ok = False
                        break
                    nxt[p] = w
                if not ok:
                    continue
                if i == 0:
                    if nxt[0] & start_bits:
                        memo[key] = ([(r0, r1)], nxt[0])
                        return memo[key]
                else:
                    reqsets.insert(0, nxt)
                    sub = search(i - 1)
                    reqsets.pop(0)
                    if sub is not None:
                        memo[key] = (sub[0] + [(r0, r1)], sub[1])
                        return memo[key]
        memo[key] = None
        return None

    try:
        result = search(n - 1)
    except TimeoutError:
        return None
    if result is None:
        return None
    routes, start_set = result
    for v in range(10):
        if v in index and (start_set >> index[v]) & 1:
            return v, routes
    # every accepted `result` has `start_set & start_bits` nonzero (the i == 0
    # acceptance check above requires it, and start_set is that same value
    # threaded back up unchanged), and start_bits is built from exactly the
    # v in range(10) with v in index, so the loop above always returns
    return None  # pragma: no cover


def _wii2d_domain(maxlen: int, cap: int) -> list[int]:
    """Return the values reachable from 0 by op strings up to ``maxlen`` long."""
    dom = {0}
    frontier = {0}
    for _ in range(maxlen):
        nxt: set[int] = set()
        for v in frontier:
            for op in _WII2D_OPS:
                w = _wii2d_apply(op, v)
                if abs(w) <= cap:
                    nxt.add(w)
        frontier = nxt
        dom |= nxt
    return sorted(dom)


def _wii2d_sequences(maxlen: int, domain: list[int]) -> list[str]:
    """All op strings up to ``maxlen`` long, deduplicated by behaviour on the domain.

    The distinct behaviours are reached by breadth-first search (each step
    appends one op and re-dedupes), rather than enumerating the full 15**maxlen
    strings, so the pool stays cheap at the lengths the search ladder needs.
    """
    size = len(domain)
    identity = tuple(range(size))  # the empty string leaves every value alone
    behaviour_index = {identity: ""}  # behaviour (on domain positions) -> op string
    frontier = [identity]
    for _ in range(maxlen):
        nxt: list[tuple[int, ...]] = []
        for b in frontier:
            for op in _WII2D_OPS:
                nb = tuple(_wii2d_apply(op, b[i]) for i in range(size))
                if nb not in behaviour_index:
                    behaviour_index[nb] = ""
                    nxt.append(nb)
        frontier = nxt
    # recover one op string per behaviour by walking BFS parents
    parent: dict[tuple[int, ...], tuple[tuple[int, ...] | None, str]] = {
        identity: (None, "")
    }
    frontier = [identity]
    for _ in range(maxlen):
        nxt = []
        for b in frontier:
            for op in _WII2D_OPS:
                nb = tuple(_wii2d_apply(op, b[i]) for i in range(size))
                if nb in behaviour_index and nb not in parent:
                    parent[nb] = (b, op)
                    nxt.append(nb)
        frontier = nxt
    out: list[str] = []
    for b in behaviour_index:
        ops: list[str] = []
        cur = b
        while (prev := parent[cur][0]) is not None:
            op = parent[cur][1]
            cur = prev
            ops.append(op)
        out.append("".join(reversed(ops)))
    return out


def _wii2d_layout(n: int, start: int, routes: list[tuple[str, str]]) -> list[str]:
    """Lay out the junction chain template.

    ``{Xi}`` placeholders on row 0, each branch's op cells on row 0 (bit 0)
    or on a dedicated detour row below (bit 1), re-merging before the next
    junction.  Merges and the final decode each leave one blank column of
    separation before what follows them.
    """
    # A junction is a single cell: the fill writes 'v' to take the 1-branch
    # or '>' to continue east, and nothing on row 0 ever occupies the column
    # after it.  The '{Xi}' spelling is four characters only because that is
    # how the placeholder is written, and instantiation gives the rest back.
    placeholder_width = 1

    placeholder_col = [0] * n
    # column 0 is always '>'; when there's a start digit (_wii2d_search only
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
        # placeholder_col[i] + 1 + len(r1).  The merge sits one blank
        # column past whichever row runs longer.
        row0_end = placeholder_width + len(r0)
        row1_end = 1 + len(r1)
        merge_col[i] = placeholder_col[i] + max(row0_end, row1_end) + 1
        if i + 1 < n:
            placeholder_col[i + 1] = merge_col[i] + 2

    decode_start = merge_col[n - 1] + 1  # one blank column past the last merge
    ascii_zero = 48
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
    Larger ``n`` searches for the branch op strings, trying lengths 2 through
    6 with increasing budgets; length 2 covers every table through three
    inputs, length 3 sampled dense tables at four, and lengths 5-6 sampled
    dense tables at five (the earlier ``n == 4`` wall was a length cap, not a
    representation limit).  The requirement sets and preimages are bit-vectors
    and routes that share a preimage effect are deduplicated, keeping the
    longer lengths tractable.  When the search cannot fit the table in its
    budget it raises :class:`ValueError` -- a genuine cap, not a
    representation limit: the counting-bound argument in :func:`_wii2d_search`
    shows no chain with bounded op strings can represent every table once
    ``n`` is large (dense non-symmetric tables past ``n == 5``), so
    large-arity tables are simply out of reach.
    """
    n = _validate_truth_table(truth_table)
    result = _wii2d_search(n, truth_table)
    if result is None:
        raise ValueError(
            "the WII2D n-embedding search found no route within its budget; "
            "dense non-symmetric tables past n == 5 are out of reach"
        )
    start, routes = result
    return "\n".join(_wii2d_layout(n, start, routes))
