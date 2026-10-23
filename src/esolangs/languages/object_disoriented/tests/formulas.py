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


def _chars(n: int, text: str) -> int:
    """min(plain bound 38T + 20, shared bound); both hold for every table."""
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
    "scaling": (_chars, False, (3, 4, 5, 6)),
    "workspace": (_workspace, False, (3, 4, 5, 6)),
}
