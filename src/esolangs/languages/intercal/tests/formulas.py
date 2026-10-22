"""INTERCAL's emitted characters: diagram nodes priced per level."""


def _digits(x: int) -> int:
    return len(str(x))


def _chars(n: int, _: str) -> int:
    """U: nodes priced per level, named nodes at most X, statements at most 2n + X.

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


FORMULAS = {"scaling": (_chars, False, (3, 4, 5, 6, 7))}
