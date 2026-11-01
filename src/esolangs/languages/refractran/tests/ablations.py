"""Isolated canonical-rule mutants; semantic IDs keep the other folds intact."""

from typing import Literal
from unittest.mock import patch

from esolangs.languages.refractran import generator

Rule = Literal["constant_fold", "ignored_input", "subtree_sharing"]


def _diagram(table: str, n: int, rule: Rule) -> tuple[list[tuple[int, int, int]], int]:
    """Return an emission DAG with one rule disabled, tracking semantics apart."""
    nodes: list[tuple[int, int, int]] = []
    seen: dict[tuple[int, int, int], int] = {}
    semantics: dict[tuple[int, int, int], int] = {}

    def walk(depth: int, lo: int, hi: int) -> tuple[int, int]:
        if depth == n:
            return int(table[lo]), int(table[lo])
        mid = (lo + hi) // 2
        (zero, sz), (one, so) = walk(depth + 1, lo, mid), walk(depth + 1, mid, hi)
        if sz == so:
            semantic = sz
            if (sz <= 1 and rule != "constant_fold") or (
                sz > 1 and rule != "ignored_input"
            ):
                return zero, semantic
        else:
            key = (depth, sz, so)
            if key not in semantics:
                semantics[key] = len(semantics) + 2
            semantic = semantics[key]
        key = (depth, zero, one)
        if rule == "subtree_sharing" or key not in seen:
            index = len(nodes) + 2
            nodes.append(key)
            if rule != "subtree_sharing":
                seen[key] = index
        else:
            index = seen[key]
        return index, semantic

    root, _ = walk(0, 0, len(table))
    return nodes, root


def ablate(table: str, rule: Rule) -> str:
    """Return the ordinary source with exactly one canonical rule disabled."""
    with patch.object(generator, "_diagram", lambda t, n: _diagram(t, n, rule)):
        return generator.refractran(table)
