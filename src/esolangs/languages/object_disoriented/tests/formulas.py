"""Object Disoriented's emitted characters: shared classes."""

from esolangs.languages.object_disoriented.generator import _HEADER


def _distinct(n: int, d: int) -> int:
    """Most non-constant subtables at depth d: a level's width or its function count."""
    return min(2**d, 2 ** (2 ** (n - d)) - 2)


def _name(count: int) -> int:
    """Longest of ``count`` names: 59 letters/digits, skipping reserved ``main``."""
    size, cap = 1, 59
    while cap - (size >= 4) < count:
        size += 1
        cap += 59**size
    return size


def _shared(n: int, _: str) -> int:
    """Shared build: each distinct non-constant subtable is written once.

    A branch used twice or more is named whenever its body exceeds 3|name|,
    so every such node (11 body characters) is a class (6 + |name| definition,
    2 + |name| a use) or a single inline object (5); constants cost at most
    their named total.  Per level the uses are 2 per parent, named nodes
    needing 2 each.
    """
    widths = [_distinct(n, d) for d in range(n)]
    s = _name(sum(widths) + 2 * n)
    total = len(_HEADER) + 5 + 11 * sum(widths)
    for d in range(n - 1):
        uses, below = 2 * widths[d], widths[d + 1]
        named = max(0, min(below, uses - below))
        once = below - named
        total += 5 * once + (6 + s) * named + (2 + s) * (uses - once)
    total += 2 * widths[n - 1] * (2 + s)
    return total + sum(2 * (8 * (n - d) + 10 + s) for d in range(1, n + 1))


def _const(m: int, body: int, s: int) -> int:
    """Characters of ``m`` uses of a constant: inline each, or named once."""
    return min(m * (5 + body), body + s + 6 + m * (s + 2)) if m else 0


def _cap(n: int, d: int) -> int:
    """Distinct non-constant subtables at depth d."""
    return _distinct(n, d)


def _profile(n: int) -> tuple[int, tuple[int, ...]]:
    """Shared build, exact for 2 <= n <= 8: the best profile of distinct counts.

    A table is a diagram: ``w_d`` distinct non-constant subtables at depth d,
    each a 11-character body with two branch slots.  Of the ``2 w_d`` slots
    ``k`` hold a constant (a child pair is never equal constants, so at most
    ``2 w_d - w_{d+1}``: every node below is used once).  With ``a = 2 w_d - k``
    slots on ``w' = w_{d+1}`` nodes, ``once = max(0, 2w' - a)`` of them used
    once cost 5 inline and the others are named (6 + s, then 2 + s a use):
    ``(6 + s) w' + (2 + s) a - (3 + 2s) once``; a constant at depth j costs
    ``_const`` with body 8(n - j) + 2 or + 4 (the generator names a branch
    exactly when that is shorter, and always a non-constant one used twice).
    Each term grows with ``s``; the names number at most
    ``sum_d min(w_{d-1}, w_d + 2) <= 53`` for n <= 8 (a named node takes two
    slots, a named constant two), so ``s = 1``.  The loop maximises over
    ``w_d <= _distinct`` (a relaxation: ignores which pairs exist), and a
    witness reconstructs its selected widths with distinct child pairs and
    reaches it. The count optimisation is verification, never a table
    emitted or consulted by the generator.
    """
    s = 1
    best: dict[int, tuple[int, tuple[int, ...]]] = {0: (0, ())}
    for d in range(n - 1, -1, -1):
        step = {}
        for w in range(1, _cap(n, d) + 1):
            options = []
            for below, (rest, profile) in best.items():
                if d == n - 1 and below:
                    continue
                reach = 0
                if below > 2 * w or (not below and w > 2):
                    continue
                for k in [2 * w] if not below else range(min(2 * w - below, w + 2) + 1):
                    a = 2 * w - k
                    once = max(0, 2 * below - a)
                    nodes = (6 + s) * below + (2 + s) * a - (3 + 2 * s) * once
                    c0 = 8 * (n - d - 1) + 2
                    consts = max(
                        _const(j, c0, s) + _const(k - j, c0 + 2, s)
                        for j in range(k + 1)
                    )
                    reach = max(reach, nodes + consts)
                options.append((11 * w + reach + rest, (w, *profile)))
            step[w] = max(options, key=lambda option: option[0])
        step[0] = (0, ())
        best = step
    value, widths = best[1]
    return len(_HEADER) + 5 + value, widths


def _worst(n: int, _: str = "") -> int:
    """The proof profile's bound; the formula corpus reconstructs its witness."""
    return _profile(n)[0]


def scaling_terms(n: int, text: str) -> dict[str, int]:
    """Price the exact low-arity profile or the shared upper envelope."""
    return {"H": _worst(n) if 2 <= n <= 8 else _shared(n, text)}


def workspace_terms(_: int, text: str) -> dict[str, int]:
    """Count code IDs that may be live in frames or cells."""
    return {"C": 3 + text.count("n") + text.count("d")}
