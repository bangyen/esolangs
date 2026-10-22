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


FORMULAS = {"scaling": (_chars, False, (3, 4, 5, 6))}
