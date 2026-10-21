"""A table cell's eight characters cannot name eight classes at every address.

A cell at address ``h`` admits the eight characters ``33 + (k - h) % 94`` for
the op indices ``k`` of XLAT1, and ``j`` lands the data pointer on the window
cell ``T + 1``.  Whatever a decoder does next is a function of that window
cell, so two characters of one table address must never share a cell class.
The window's conflict graph (cells whose offsets differ by a difference of
two op indices) therefore has to be properly coloured.  Its independence
number is 8, so a proper colouring needs at least ``ceil(94 / 8) = 12``
classes: eight classes, three bits per cell, are impossible.
"""

from __future__ import annotations

from esolangs.languages.malbolge.interpreter import _XLAT1

_CELLS = 94
_OPS = sorted(_XLAT1.index(op) for op in "ji*p</vo")
_DIFFERENCES = sorted({(a - b) % _CELLS for a in _OPS for b in _OPS if a != b})


def _neighbours() -> list[int]:
    """Bitmask per window cell of the cells some address pairs it with."""
    masks = [0] * _CELLS
    for cell in range(_CELLS):
        for d in _DIFFERENCES:
            masks[cell] |= 1 << ((cell + d) % _CELLS)
    return masks


def _independence_number() -> int:
    masks = _neighbours()
    best = 0

    def grow(candidates: int, size: int) -> None:
        nonlocal best
        best = max(best, size)
        while candidates and size + candidates.bit_count() > best:
            cell = (candidates & -candidates).bit_length() - 1
            candidates &= ~(1 << cell)
            grow(candidates & ~masks[cell], size + 1)

    grow((1 << _CELLS) - 1, 0)
    return best


def test_every_address_pairs_its_characters() -> None:
    """Each address's eight window cells are pairwise in conflict."""
    masks = _neighbours()
    for h in range(_CELLS):
        cells = [(k - h) % _CELLS for k in _OPS]
        assert len(set(cells)) == 8
        for a in cells:
            for b in cells:
                assert a == b or masks[a] >> b & 1


def test_eight_classes_cannot_be_distinct_everywhere() -> None:
    """At most eight cells share a class, so eight classes cover 64 < 94 cells."""
    assert _independence_number() == 8
    assert 8 * _independence_number() < _CELLS
