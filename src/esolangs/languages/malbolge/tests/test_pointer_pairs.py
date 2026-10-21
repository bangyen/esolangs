"""The cascade's pointer pairs are the fewest that cover both answer labels.

A pair at ``a`` labels the characters ``a - 1`` (answer 1) and ``a``
(answer 0).  Every table residue ``h`` must admit a character of each
label among the eight the loader accepts there, and a pair cannot sit on a
mixer, helper or NEXT cell or overlap another pair.  Under those
constraints the exhaustive search below finds exactly one cover of the
minimum size, seventeen pairs: the shipped ``_PAIRS``.
"""

from __future__ import annotations

from esolangs.languages.malbolge.generator.cascade import (
    _C_HELPERS,
    _C_INITS,
    _NEXTS,
    _PAIRS,
)
from esolangs.languages.malbolge.generator.isa import _ACTIVE, _first_free
from esolangs.languages.malbolge.interpreter import _XLAT1

_RESIDUES = 94
_OPS = [_XLAT1.index(op) for op in _ACTIVE]


def _placed() -> set[int]:
    """The mixer and helper cells, placed as ``_head`` places them."""
    taken: set[int] = set()
    for value in (*_C_INITS, *_C_HELPERS.values()):
        taken.add(_first_free(value, 34, 128, taken))
    return taken


def _requirements(candidates: set[int]) -> list[frozenset[int]]:
    """Per residue and label, the candidate pair starts that would serve it."""
    needs = set()
    for h in range(_RESIDUES):
        chars = [33 + (k - h) % _RESIDUES for k in _OPS]
        needs.add(frozenset(t + 1 for t in chars) & candidates)  # label 1
        needs.add(frozenset(chars) & candidates)  # label 0
    return list(needs)


def _minimum_covers() -> tuple[int, list[tuple[int, ...]]]:
    """The smallest cover size and every cover of that size."""
    taken = _placed()
    nexts = set(_NEXTS)
    candidates = {
        a
        for a in range(34, 127)
        if a not in taken and a + 1 not in taken and not {a - 1, a, a + 1} & nexts
    }
    requirements = _requirements(candidates)
    best: list[int] = [len(candidates) + 1]
    covers: list[tuple[int, ...]] = []

    def search(chosen: frozenset[int], uncovered: list[frozenset[int]]) -> None:
        if not uncovered:
            if len(chosen) < best[0]:
                best[0] = len(chosen)
                covers.clear()
            covers.append(tuple(sorted(chosen)))
            return
        if len(chosen) >= best[0]:
            return
        blocked = chosen | {a + 1 for a in chosen} | {a - 1 for a in chosen}
        need = min(uncovered, key=lambda r: len(r - blocked))
        for a in sorted(need - blocked):
            picked = chosen | {a}
            search(picked, [r for r in uncovered if not r & picked])

    search(frozenset(), requirements)
    return best[0], covers


def test_pairs_are_the_unique_minimum_cover() -> None:
    size, covers = _minimum_covers()
    assert size == 17
    assert covers == [_PAIRS]
