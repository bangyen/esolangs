"""INTERCAL's emitted characters: diagram nodes priced per level."""

from math import isqrt


def _digits(x: int) -> int:
    return len(str(x))


def _bound(n: int, _: str) -> int:
    """V: nodes priced per level, named nodes at most X, statements at most 2n + X.

    X = min(T/8 + 2, T/16 + 14), the Execution bound's named nodes.  Names past
    .65535 spill to ``,j SUB #i`` arrays: each reference and ``<-`` target costs at
    most 6 more characters, and each of the A arrays a ``DO ,j <- #B`` statement.
    """
    count, below = [0] * n, 2
    for level in range(n - 1, -1, -1):
        count[level] = min(1 << level, below * (below - 1))
        below += count[level]
    nodes = sum(count)
    named = min(min(((1 << n) >> 3) + 2, ((1 << n) >> 4) + 14), nodes)
    spilled = max(0, 2 * n - 2 + named - 65535)
    arrays = -(-spilled // (isqrt(spilled - 1) + 1)) if spilled else 0
    statements = 2 * n + named + arrays
    neg_name = _digits(2 * n - 2)
    name = _digits(2 * n - 2 + named)

    def sel(level: int) -> int:
        return 1 + _digits(n - level)

    total = 0
    for level in range(n):
        inline = 38 + 2 * sel(level)  # ~selector inline: 27 + (sel + 11) + sel
        if 2 <= level <= n - 2:
            total += max(
                count[level] * (28 + neg_name + sel(level)),
                min(count[level], 2) * inline,
            )
        else:
            total += count[level] * inline
    # Child names; two constant edges at least.
    total += 4 + (nodes + named - 1) * (1 + name)
    total += named * (5 + name)  # ".k <- " of each named node
    if spilled:
        total += 6 * (nodes + 2 * named - 1) + arrays * (14 + 2 * _digits(spilled))
    polite = max(1, (statements + 4) // 5)
    # PLEASE/DO, space, newline.
    total += 6 * polite + 2 * (statements - polite) + 2 * statements - 1
    total += sum(7 + _digits(n - i) for i in range(n))  # ".k <- @@"
    # The named ~selector.
    total += sum(5 + neg_name + sel(level) + 11 for level in range(2, n - 1))
    # Result, READ OUT, GIVE UP.
    return total + (6 + _digits(n + 1)) + (10 + _digits(n + 1)) + 7


def _capped(n: int) -> int:
    """U at n = 11..19: a full tree to level n - 4, 240 nodes at n - 3 over all 16 ids.

    Every id is read 30 times by level n - 3, so the 12 pair nodes are named.
    The 2^(n-3) - 240 spare slots above re-read level n - 3 nodes (named at
    two reads, all 240 at n = 12: a statement and a name beat a constant or a
    named pair node), the rest on the longest names.  The witness is built to
    n = 19; at n = 20 this shape ends, since level n - 4 would need 2**16
    distinct parents and the capped level holds only 240 * 239 ordered
    pairs — the successor one level down is :func:`_shifted`.  The shape
    was climbed, not solved as the n <= 10 program is.
    """
    slots = 1 << (n - 3)
    count = [*(1 << level for level in range(n - 3)), 240, 12, 2]
    named = min(240, slots - 240)  # level n - 3 nodes read twice
    extra = slots - 240 - named  # third reads
    negs = n - 3
    first = n + 2 + negs
    statements = n + negs + 14 + named + 3
    polite = max(1, (statements + 4) // 5)
    total = 0
    for level in range(n):
        sel = 1 + _digits(n - level)
        if 2 <= level <= n - 2:
            neg = _digits(2 * n - level)
            total += count[level] * (28 + neg + sel) + 16 + neg + sel
        else:
            total += count[level] * (38 + 2 * sel)
    a, b = 1 + _digits(first), 1 + _digits(first + 1)
    # Level n - 2: 12 pairs of A, B and two constants; the bottom two read constants.
    total += 2 * (a + b) + 4 * (b + 2) + 4 * (a + 2) + 2 * 4 + 8
    ref = [1 + _digits(first + i) for i in range(14 + named)]
    total += 30 * (a + b + 4 + sum(ref[2:14]))  # level n - 3: 480 reads
    total += 2 * sum(ref[14:]) + extra * ref[-1]  # level n - 4's slots
    total += sum(5 + _digits(first + i) for i in range(14 + named))  # ".k <- "
    total += sum(7 + _digits(n - i) for i in range(n))  # ".k <- @@"
    total += (5 + _digits(n + 1)) + (10 + _digits(n + 1)) + 7
    return total + 4 * statements + 4 * polite - 1


def _target_sum(lo: int, hi: int, width: int) -> int:
    """Sum of name-spelling lengths over the consecutive names lo..hi.

    Scalar names cost 1 + digits; spilled names (past .65535) cost
    digits(j) + digits(i) + 7 for the element ``,j SUB #i``.
    """
    total = 0
    top = min(hi, 65535)
    start = lo
    while start <= top:
        block = min(top, 10 ** _digits(start) - 1)
        total += (block - start + 1) * (1 + _digits(start))
        start = block + 1
    if hi > 65535:
        for j in range(1, (hi - 65536) // width + 2):
            first_i = max(0, lo - 65536 - (j - 1) * width) if j == 1 else 0
            last_i = min(width - 1, hi - 65536 - (j - 1) * width)
            if last_i < first_i:
                continue
            total += (last_i - first_i + 1) * (_digits(j) + 7)
            total += sum(_digits(i + 1) for i in range(first_i, last_i + 1))
    return total


def _plateau(n: int) -> int:
    """U at n >= 22: the shifted cap under a plateau at level n - 5.

    Level n - 5 holds 2^(n-6) distinct pairs of capped nodes, each
    read twice and named, so the capped level's 2^(n-5) reads spread
    r0 = 2^(n-5) // 65,280 per node with one more on the last rem
    (the longest names): at n = 22 the {2, 3} spread, at n = 23 the
    {4, 5}.  Against :func:`_shifted`'s full level n - 5 this gives
    up half the capped reads and 2^(n-6) frames, and gains the
    plateau's statements and second spellings: at n = 22 a converted
    pair nets 3 * spelling + 4 + prefix share - inline > 0
    (spillings run to 12-13 characters against an inline of 44), at
    n = 20 and 21 it does not, and the full level stands there; at
    n = 23 the margin over the shifted shape is 310,847 characters
    and a width sweep over level n - 5 peaks at the plateau width.
    Priced like :func:`_shifted`, with both named levels' reads
    spelled out.
    """
    cap = 65280
    x = 1 << (n - 6)
    negs = n - 3
    first = n + 2 + negs
    named = 254 + cap + x
    top = first + named - 1
    spilled = top - 65535
    width = isqrt(spilled - 1) + 1 if spilled > 0 else 0
    arrays = (spilled - 1) // width + 1 if spilled > 0 else 0
    statements = n + negs + named + 3 + arrays
    polite = max(1, (statements + 4) // 5)

    def frame(level: int) -> int:
        sel = 1 + _digits(n - level)
        if 2 <= level <= n - 2:
            return 28 + _digits(2 * n - level) + sel
        return 38 + 2 * sel

    count = [*(1 << level for level in range(n - 5)), x, cap, 240, 12, 2]
    total = sum(count[level] * frame(level) for level in range(n))

    def ref2(y: int) -> int:
        return 2 if y in (0, 3) else 1 + _digits(first + y - 1)

    def ref4(v: int) -> int:
        if v % 5 == 0:
            return ref2(v // 5)
        return 1 + _digits(first + 2 + v - (v - 1) // 5 - 1)

    def ref8(v: int) -> int:
        if v % 17 == 0:
            return ref4(v // 17)
        return 1 + _digits(first + 14 + v - (v - 1) // 17 - 1)

    b2 = 4 + sum(1 + _digits(first + i) for i in range(2))
    s4 = _target_sum(first + 2, first + 13, width) + b2
    s8 = _target_sum(first + 14, first + 253, width) + s4
    total += 8 + 6 * b2 + 30 * s4 + 510 * s8
    cap_lo = first + 254
    cap_hi = cap_lo + cap - 1
    r0, rem = divmod(2 * x, cap)
    total += r0 * _target_sum(cap_lo, cap_hi, width)  # capped reads
    if rem:
        total += _target_sum(cap_hi - rem + 1, cap_hi, width)  # extra reads
    total += 2 * _target_sum(cap_hi + 1, top, width)  # plateau reads
    total += _target_sum(first, top, width) + 4 * named  # ".k <- "
    for level in range(2, n - 1):  # the named ~selector statements
        total += 16 + _digits(2 * n - level) + 1 + _digits(n - level)
    if arrays:
        total += sum(_digits(j) + _digits(width) + 6 for j in range(1, arrays + 1))
    total += sum(7 + _digits(n - i) for i in range(n))  # ".k <- @@"
    total += (5 + _digits(n + 1)) + (10 + _digits(n + 1)) + 7
    return total + 4 * statements + 4 * polite - 1


def _shifted(n: int) -> int:
    """U at n = 20..21: the shifted cap — level n - 4 holds all 65,280 pairs.

    The capped shape of :func:`_capped` ends at 19 because its level
    n - 4 draws distinct parents from 240 * 239 pairs.  One level down
    the supply is every ordered pair of distinct eight-row values:
    256 ids below (240 pair nodes, 12, 2 and the two constants) give
    65,280 nodes at level n - 4, under the 2^(n-4) occurrences, so
    level n - 5 stays full and the cap recursion's counts are
    [2^l, 65,280, 240, 12, 2].  The 2^(n-4) reads of the capped level
    spread r0 = 2^(n-4) // 65,280 per node with one more on the last
    rem nodes (the longest names): at n = 20 only the 256 twice-read
    nodes are named, from n = 21 every capped node is named and the
    dearest names spill.  Every node renders exactly once — named
    nodes in their statement, the rest have the one reader their
    parent — so the total is all frames, all edge masses and the
    statement scaffolding, priced below in _capped's style.

    The bottom edge masses are value-class sums: an eight-row value
    is read 510 times by the capped level, a four-row value 30 times
    by level n - 3, a two-row value 6 times by level n - 2, at the
    spelling of the id it resolves to (degenerate values alias to
    their half's id, constants cost 2).
    """
    cap = 65280
    slots = 1 << (n - 4)
    r0, rem = divmod(slots, cap)
    negs = n - 3
    first = n + 2 + negs
    named_cap = cap if r0 >= 2 else rem
    named = 254 + named_cap
    top = first + named - 1
    spilled = top - 65535
    width = isqrt(spilled - 1) + 1 if spilled > 0 else 0
    arrays = (spilled - 1) // width + 1 if spilled > 0 else 0
    statements = n + negs + named + 3 + arrays
    polite = max(1, (statements + 4) // 5)

    def frame(level: int) -> int:
        sel = 1 + _digits(n - level)
        if 2 <= level <= n - 2:
            return 28 + _digits(2 * n - level) + sel
        return 38 + 2 * sel

    count = [*(1 << level for level in range(n - 4)), cap, 240, 12, 2]
    total = sum(count[level] * frame(level) for level in range(n))

    def ref2(y: int) -> int:  # two-row value; 00 and 11 are constants
        return 2 if y in (0, 3) else 1 + _digits(first + y - 1)

    def ref4(x: int) -> int:  # four-row value; x = 5y aliases to ref2
        if x % 5 == 0:
            return ref2(x // 5)
        return 1 + _digits(first + 2 + x - (x - 1) // 5 - 1)

    def ref8(v: int) -> int:  # eight-row value; v = 17x aliases to ref4
        if v % 17 == 0:
            return ref4(v // 17)
        return 1 + _digits(first + 14 + v - (v - 1) // 17 - 1)

    b2 = 4 + sum(1 + _digits(first + i) for i in range(2))
    s4 = _target_sum(first + 2, first + 13, width) + b2
    s8 = _target_sum(first + 14, first + 253, width) + s4
    total += 8 + 6 * b2 + 30 * s4 + 510 * s8
    cap_lo = first + 254
    cap_hi = first + 254 + named_cap - 1
    if r0 >= 2:  # capped reads, dearest spellings on the extra reads
        total += r0 * _target_sum(cap_lo, cap_hi - rem, width)
        total += (r0 + 1) * _target_sum(cap_hi - rem + 1, cap_hi, width)
    else:
        total += 2 * _target_sum(cap_lo, cap_hi, width)
    total += _target_sum(first, cap_hi, width) + 4 * named  # ".k <- "
    for level in range(2, n - 1):  # the named ~selector statements
        total += 16 + _digits(2 * n - level) + 1 + _digits(n - level)
    if arrays:
        total += sum(_digits(j) + _digits(width) + 6 for j in range(1, arrays + 1))
    total += sum(7 + _digits(n - i) for i in range(n))  # ".k <- @@"
    total += (5 + _digits(n + 1)) + (10 + _digits(n + 1)) + 7
    return total + 4 * statements + 4 * polite - 1


def _chars(n: int, program: str) -> int:
    """U: the most nodes per level; exact for n = 3..23.

    From n = 11 level n - 3 holds its 240 distinct pairs (:func:`_capped`);
    from n = 20 the cap shifts one level down (:func:`_shifted`), from
    n = 22 under a named plateau (:func:`_plateau`); past n = 23 the
    bound V.
    Exact because the generator's cost is a function of per-level node, named
    and constant-edge counts, and an integer program over them maximises at
    U: each level's nodes are at most the Hall slots above (q <= nodes above
    + 1) and the distinct ordered pairs below, constant edges are at least
    the pairs with no node to use, and spare readers at levels <= j fit the
    slots above j.  A node is named iff it has two readers.

    A node named costs two edges that a fresh node would use, so only the 2
    bottom nodes and the pair nodes the spare edges reach are read twice.
    At the shifted cap the reads are forced onto every node once before
    any node is read twice: crossing a fresh node into named gains its
    statement and a spelling, against the one spelling the donor loses.
    """
    if n > 23:
        return _bound(n, program)
    if n >= 22:
        return _plateau(n)
    if n > 19:
        return _shifted(n)
    if n > 10:
        return _capped(n)
    pair = min(1 << (n - 2), 12)
    count = [*(1 << level for level in range(n - 2)), pair, 2]
    twice = max(0, min(12, (1 << (n - 2)) - 12))
    spare = max(0, (1 << (n - 2)) - pair - twice)
    named, negs = 2 + twice, n - 3
    first = n + 2 + negs
    statements = n + 3 + negs + named
    polite = max(1, (statements + 4) // 5)
    total = 0
    for level in range(n):
        sel = 1 + _digits(n - level)
        if 2 <= level <= n - 2 and count[level] >= 3:
            neg = _digits(2 * n - level)  # numbered bottom-up from n + 2
            total += count[level] * (28 + neg + sel) + 16 + neg + sel
        else:
            total += count[level] * (38 + 2 * sel)
    # Level n - 2 pairs, dearest first: A B, B A, B and a constant, A and one.
    a, b = 1 + _digits(first), 1 + _digits(first + 1)
    pairs = sorted([a + b] * 2 + [b + 2] * 4 + [a + 2] * 4 + [4] * 2, reverse=True)
    total += sum(pairs[:pair]) + 8  # the 2 bottom nodes read only constants
    total += (2 * twice) * (1 + _digits(first + 2)) + spare * b
    total += sum(5 + _digits(first + i) for i in range(named))  # ".k <- "
    total += sum(7 + _digits(n - i) for i in range(n))  # ".k <- @@"
    # Result, READ OUT, GIVE UP, statement keywords, spaces and newlines.
    total += (5 + _digits(n + 1)) + (10 + _digits(n + 1)) + 7
    return total + 4 * statements + 4 * polite - 1


FORMULAS = {"scaling": (_chars, frozenset(range(3, 24)), tuple(range(3, 25)))}
