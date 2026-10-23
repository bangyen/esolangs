"""Object Disoriented's emitted characters: plain tree or shared classes."""

from esolangs.languages.object_disoriented.generator import _HEADER


def _distinct(n: int, d: int) -> int:
    """Most non-constant subtables at depth d: a level's width or its function count."""
    return min(2**d, 2 ** (2 ** (n - d)) - 2)


def _name(count: int) -> int:
    """Characters of the longest name among ``count`` (60 one-char, then 60^2, ...)."""
    size, cap = 1, 60
    while cap < count:
        size += 1
        cap += 60**size
    return size


def _shared(n: int, _: str) -> int:
    """Shared build: each distinct non-constant subtable is written once.

    A branch used twice or more is named whenever its body exceeds 3|name| + 1,
    so every such node (25 body characters) is a class (7 + |name| definition,
    2 + |name| a use) or a single inline object (5); constants cost at most
    their named total.  Per level the uses are 2 per parent, named nodes
    needing 2 each.
    """
    widths = [_distinct(n, d) for d in range(n)]
    s = _name(sum(widths) + 2 * n)
    total = len(_HEADER) + 5 + 25 * sum(widths)
    for d in range(n - 1):
        uses, below = 2 * widths[d], widths[d + 1]
        named = max(0, min(below, uses - below))
        once = below - named
        total += 5 * once + (7 + s) * named + (2 + s) * (uses - once)
    total += 2 * widths[n - 1] * (2 + s)
    return total + sum(2 * (8 * (n - d) + 11 + s) for d in range(1, n + 1))


def _const(m: int, body: int, s: int) -> int:
    """Characters of ``m`` uses of a constant: inline each, or named once."""
    return min(m * (5 + body), body + s + 7 + m * (s + 2)) if m else 0


def _cap(n: int, d: int) -> int:
    """Distinct non-constant subtables at depth d."""
    return _distinct(n, d)


def _worst(n: int, _: str = "") -> int:
    """Shared build, exact for 2 <= n <= 8: the best profile of distinct counts.

    A table is a diagram: ``w_d`` distinct non-constant subtables at depth d,
    each a 25-character body with two branch slots.  Of the ``2 w_d`` slots
    ``k`` hold a constant (a child pair is never equal constants, so at most
    ``2 w_d - w_{d+1}``: every node below is used once).  With ``a = 2 w_d - k``
    slots on ``w' = w_{d+1}`` nodes, ``once = max(0, 2w' - a)`` of them used
    once cost 5 inline and the others are named (7 + s, then 2 + s a use):
    ``(7 + s) w' + (2 + s) a - (4 + 2s) once``; a constant at depth j costs
    ``_const`` with body 8(n - j) + 2 or + 4 (the generator names a branch
    exactly when that is shorter, and always a non-constant one used twice).
    Each term grows with ``s``; the names number at most
    ``sum_d min(w_{d-1}, w_d + 2) <= 53`` for n <= 8 (a named node takes two
    slots, a named constant two), so ``s = 1``.  The loop maximises over
    ``w_d <= _distinct`` (a relaxation: ignores which pairs exist), and a
    witness reaches it: levels above the knee a full tree, the knee pairing
    the slots left over with two constants each, below it every function.
    """
    s = 1
    best = {0: 0}  # best[w]: levels from d down, given w nodes at depth d
    for d in range(n - 1, -1, -1):
        step = {}
        for w in range(1, _cap(n, d) + 1):
            options = []
            for below, rest in best.items():
                if d == n - 1 and below:
                    continue
                reach = 0
                if below > 2 * w or (not below and w > 2):
                    continue
                for k in [2 * w] if not below else range(min(2 * w - below, w + 2) + 1):
                    a = 2 * w - k
                    once = max(0, 2 * below - a)
                    nodes = (7 + s) * below + (2 + s) * a - (4 + 2 * s) * once
                    c0 = 8 * (n - d - 1) + 2
                    consts = max(
                        _const(j, c0, s) + _const(k - j, c0 + 2, s)
                        for j in range(k + 1)
                    )
                    reach = max(reach, nodes + consts)
                options.append(25 * w + reach + rest)
            step[w] = max(options)
        step[0] = 0
        best = step
    return len(_HEADER) + 5 + best[1]


def _chars(n: int, text: str) -> int:
    """min(plain bound 38T + 20, shared bound); both hold for every table."""
    if 2 <= n <= 8:
        return _worst(n)
    return min(38 * 2**n + 20, _shared(n, text))


def _workspace(n: int, text: str) -> int:
    """Frames + store + cell count + 14 + input count, each bounded by its own shape.

    A run nests 2n + 3 calls at most, alternating the bit object's or ``N``'s
    one-line body (<= 9 ops) with a branch body (<= 16n + 40 ops); a call's
    cells, 6n + 9 at most, are numbered below the cell count, so a frame at
    depth j holds code, pc and three refs (a slot adds a bit).  Its stack is
    empty but at the innermost call (<= 3 items).  A cell is z, a bit or an
    ``N`` object (c, 0, 0) or a branch object (c, N, 0): at most one of the
    last two and a bit per level, the rest 1 bit each.  ``c`` bounds the code
    ids: three built-ins and one per ``n`` form or class.  ``in_bits`` and
    ``out_bits`` peak at 7 bits each.
    """
    bl = int.bit_length
    c = 3 + text.count("n") + text.count("d")
    cells = 6 * n + 9
    frames = sum(
        bl(c)
        + (4 if j % 2 == 0 else bl(16 * n + 40))
        + 3 * (bl(6 * ((j + 1) // 2) + 9) + 1)
        for j in range(2 * n + 3)
    )
    frames += 4 * bl(cells) + 5
    store = (n + 1) * (3 * bl(c) + 6) + cells
    return frames + store + bl(cells) + bl(n) + 14


FORMULAS = {
    "scaling": (_chars, frozenset(range(2, 9)), tuple(range(2, 10))),
    "workspace": (_workspace, False, (3, 4, 5, 6)),
}
