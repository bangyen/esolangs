"""INTERCAL's emitted characters: diagram nodes priced per level."""


def _digits(x: int) -> int:
    return len(str(x))


def _bound(n: int, _: str) -> int:
    """V: nodes priced per level, named nodes at most X, statements at most 2n + X.

    X = min(T/8 + 2, T/16 + 14), the Execution bound's named nodes.
    """
    count, below = [0] * n, 2
    for level in range(n - 1, -1, -1):
        count[level] = min(1 << level, below * (below - 1))
        below += count[level]
    nodes = sum(count)
    named = min(min(((1 << n) >> 3) + 2, ((1 << n) >> 4) + 14), nodes)
    statements = 2 * n + named
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
    polite = max(1, (statements + 4) // 5)
    # PLEASE/DO, space, newline.
    total += 6 * polite + 2 * (statements - polite) + 2 * statements - 1
    total += sum(7 + _digits(n - i) for i in range(n))  # ".k <- @@"
    # The named ~selector.
    total += sum(5 + neg_name + sel(level) + 11 for level in range(2, n - 1))
    # Result, READ OUT, GIVE UP.
    return total + (6 + _digits(n + 1)) + (10 + _digits(n + 1)) + 7


def _chars(n: int, program: str) -> int:
    """U: a full tree to level n - 3 over 12 and 2, the most nodes; exact for n = 3..10.

    Past n = 10 the bound V (level n - 3 outgrows its 240 distinct pairs).
    Exact because the generator's cost is a function of per-level node, named
    and constant-edge counts, and an integer program over them maximises at
    U: each level's nodes are at most the Hall slots above (q <= nodes above
    + 1) and the distinct ordered pairs below, constant edges are at least
    the pairs with no node to use, and spare readers at levels <= j fit the
    slots above j.  A node is named iff it has two readers.

    A node named costs two edges that a fresh node would use, so only the 2
    bottom nodes and the pair nodes the spare edges reach are read twice.
    """
    if n > 10:
        return _bound(n, program)
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


FORMULAS = {"scaling": (_chars, frozenset(range(3, 11)), tuple(range(3, 12)))}
