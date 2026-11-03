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


def _neighbours(
    cells: int = _CELLS, offsets: tuple[int, ...] = tuple(_OPS)
) -> list[int]:
    """Bitmask per window cell of the cells some address pairs it with."""
    differences = {(a - b) % cells for a in offsets for b in offsets if a != b}
    masks = [0] * cells
    for cell in range(cells):
        for d in differences:
            masks[cell] |= 1 << ((cell + d) % cells)
    return masks


def _independence_number(
    cells: int = _CELLS, offsets: tuple[int, ...] = tuple(_OPS)
) -> int:
    masks = _neighbours(cells, offsets)
    best = 0

    def grow(candidates: int, size: int) -> None:
        nonlocal best
        best = max(best, size)
        while candidates and size + candidates.bit_count() > best:
            cell = (candidates & -candidates).bit_length() - 1
            candidates &= ~(1 << cell)
            grow(candidates & ~masks[cell], size + 1)

    grow((1 << cells) - 1, 0)
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


def test_period_47_cannot_cover_seven_meanings() -> None:
    """Each covering class needs seven points, so seven classes need 49 > 47.

    Six points give 48 incidences across 47 translates: covering all leaves
    one doubled translate. Removing one endpoint leaves five independent
    points, contradicting alpha=4. Smaller classes cannot cover 47 at all.
    """
    cells = _CELLS // 2
    assert len({op % cells for op in _OPS}) == 8
    masks = _neighbours(cells)
    witness = (0, 7, 14, 21)
    assert all(not (masks[a] >> b & 1) for a in witness for b in witness if a != b)
    assert _independence_number(cells) == len(witness) == 4


def test_parity_sheets_need_thirteen_disagreements() -> None:
    """A class covers at most 6a + 4b + 4 shifts for a pairs and b singles."""
    offsets = tuple(sorted({op // 2 for op in _OPS}))
    assert len(offsets) == 7
    masks = _neighbours(47, offsets)
    witness = (0, 2, 4, 6)
    assert all(not (masks[a] >> b & 1) for a in witness for b in witness if a != b)
    assert _independence_number(47, offsets) == len(witness) == 4
