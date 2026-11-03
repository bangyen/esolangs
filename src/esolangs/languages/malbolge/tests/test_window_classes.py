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

from functools import cache
from itertools import combinations, combinations_with_replacement

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


def test_parity_conditioned_meaning_needs_thirteen_entries() -> None:
    """Twelve four-shift blocks would cover 47 shifts with one overlap."""
    cells = _CELLS // 2
    offsets = [tuple(op // 2 for op in _OPS if op % 2 == sheet) for sheet in (0, 1)]
    blocks = [
        sum(1 << ((index - op) % cells) for op in sheet)
        for sheet in offsets
        for index in range(cells)
    ]
    containing = [[block for block in blocks if block >> i & 1] for i in range(cells)]

    def tiles(remaining: int) -> bool:
        if not remaining:
            return True
        choices = min(
            (
                [block for block in containing[i] if block & remaining == block]
                for i in range(cells)
                if remaining >> i & 1
            ),
            key=len,
        )
        return any(tiles(remaining ^ block) for block in choices)

    assert blocks[0] & blocks[1] == 0
    assert tiles(blocks[0] | blocks[1])
    # Translate the sole overlap to zero. The other ten blocks must tile
    # the remaining forty shifts exactly.
    full = (1 << cells) - 1
    roots = [(a, b) for a, b in combinations(containing[0], 2) if a & b == 1]
    assert len(roots) == 20
    assert not any(tiles(full ^ (a | b)) for a, b in roots)


def test_shifted_relabeling_fixed_colors_need_eight_entries() -> None:
    """A fixed color must cover the union of the shifted offset sets."""
    cells = _CELLS // 2
    full = (1 << cells) - 1
    even, odd = ({op // 2 for op in _OPS if op % 2 == sheet} for sheet in (0, 1))

    def covers(offsets: set[int], size: int) -> bool:
        blocks = [sum(1 << ((i - op) % cells) for op in offsets) for i in range(cells)]
        containing = [
            [block for block in blocks if block >> i & 1] for i in range(cells)
        ]
        width = len(offsets)

        @cache
        def fit(left: int, slots: int) -> bool:
            if not left:
                return True
            needed = left.bit_count()
            if needed > slots * width:
                return False
            minimum = needed - (slots - 1) * width
            choices = min(
                (
                    [
                        block
                        for block in containing[i]
                        if (block & left).bit_count() >= minimum
                    ]
                    for i in range(cells)
                    if left >> i & 1
                ),
                key=len,
            )
            return any(fit(left & ~block, slots - 1) for block in choices)

        # Translate a chosen position to zero.
        return fit(full & ~blocks[0], size - 1)

    assert covers(set(range(7)), 7)
    for shift in range(cells):
        offsets = even | {(op + shift) % cells for op in odd}
        assert not covers(offsets, 7)
        if len(offsets) == 6:
            assert not covers(offsets, 8)


def test_equal_steps_force_alternating_sheet_swaps() -> None:
    """Three vacancies force occupied pairs at distances d and 7-d."""
    cells = _CELLS // 2
    checked = 0
    for a, b in combinations_with_replacement(range(cells), 2):
        vacancies = [0] * cells
        for i in (0, a, b):
            vacancies[i] += 1
        if vacancies[0] == 3:
            continue
        # Subtract adjacent seven-column occupancy sums.
        counts = [0] * cells
        for k in range(1, cells):
            i = 7 * k % cells
            counts[i] = counts[(i - 7) % cells] + vacancies[i - 1] - vacancies[i]
        offset, remainder = divmod(13 - sum(counts), cells)
        counts = [count + offset for count in counts]
        if remainder or min(counts) < 0 or max(counts) > 2:
            continue
        assert max(counts) == 1
        distances = {
            d
            for d in range(1, 7)
            if any(counts[i] and counts[(i + d) % cells] for i in range(cells))
        }
        assert any(7 - d in distances for d in distances)
        checked += 1
    assert checked == 105


def test_alternating_seven_class_orbit_cannot_cover() -> None:
    """A thirteen-point shape has thirteen gaps of seven plus three extras."""
    cells = _CELLS // 2
    offsets = [tuple(op // 2 for op in _OPS if op % 2 == sheet) for sheet in (0, 1)]

    full = (1 << cells) - 1

    def mask(points: list[int], step: int, sheet: int, ops: tuple[int, ...]) -> int:
        return sum(
            1 << i
            for i in {
                (point * step - op) % cells
                for point in points
                if point % 2 == sheet
                for op in ops
            }
        )

    def shift(bits: int, distance: int) -> int:
        return ((bits << distance) | (bits >> (cells - distance))) & full

    assert all(
        mask(list(range(_CELLS)), 1, s, ops) == full for s in (0, 1) for ops in offsets
    )
    assert shift(1 << (cells - 1), 1) == 1
    assert len({7 * i + k for i in range(13) for k in range(7)}) == 91
    for extra in combinations_with_replacement(range(13), 3):
        points = [0]
        for i in range(12):
            points.append(points[-1] + 7 + extra.count(i))
        for step in range(1, cells):
            ea, eb = (mask(points, step, s, offsets[0]) for s in (0, 1))
            oa, ob = (mask(points, step, s, offsets[1]) for s in (0, 1))
            assert not any(
                ea | shift(ob, delta) == full and eb | shift(oa, delta) == full
                for delta in range(cells)
            )
