"""Independent trees with one canonical, spelling or sibling rule disabled."""

from functools import cache
from typing import Literal

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.languages.retrograde.generator import _moves

Rule = Literal[
    "default",
    "constant_fold",
    "ignored_input",
    "inverse_moves",
    "bidirectional_sibling",
]


def ablate(table: str, rule: Rule) -> str:
    """Return the native tree with exactly the named rule disabled."""
    n = _validate_truth_table(table)
    ids = subtree_ids(table)
    constants = rule != "constant_fold"
    prefix = "$>" * n
    if constants and ids[0][0] < 2:
        return prefix + ("*" if ids[0][0] else "")
    fresh = max(map(max, ids)) + 1
    ranks = [
        {
            tuple(ids[d + 1][2 * k : 2 * k + 2]): f
            for k, f in enumerate(ids[d])
            if f >= 2
        }
        for d in range(n)
    ]

    def intern(depth: int, low: int, high: int) -> int:
        nonlocal fresh
        if low == high and low < 2:
            return low
        key = low, high
        if key not in ranks[depth]:
            ranks[depth][key] = fresh
            fresh += 1
        return ranks[depth][key]

    @cache
    def tree(depth: int, k: int) -> tuple[str, int]:
        node = ids[depth][k]
        if depth == n or (constants and node < 2):
            return (
                ">" * (n - depth) + "*" + "<" * (n - depth) if node else "",
                node,
            )
        zero, one = 2 * k, 2 * k + 1
        zf, of = ids[depth + 1][zero], ids[depth + 1][one]
        z, zb = tree(depth + 1, zero)
        o, ob = tree(depth + 1, one)
        if rule != "ignored_input" and node >= 2 and zf == of:
            return ">" + z + "<", intern(depth, zb, zb)
        if rule != "bidirectional_sibling" and zf != of:
            if zf < 2 and of < 2:
                return (
                    "*{"
                    + ">" * (n - depth)
                    + ("/" if of else "\\")
                    + "<" * (n - depth)
                    + "}*",
                    intern(depth, of, zf),
                )
            if ob == zf:
                return "*{>" + o + "<}*", intern(depth, of, zf)
        high = ">" + o + "<" if not constants or of else ""
        low = ">" + z + "<" if not constants or zf else ""
        return "*{{*" + high + "}{*" + low + "}}", intern(depth, zb, ob)

    source = prefix + "<" * n + tree(0, 0)[0] + ">" * n
    return source if rule == "inverse_moves" else _moves(source)
