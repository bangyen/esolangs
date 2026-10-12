"""Exact rendered length of a wire layout, without painting the grid."""

from __future__ import annotations

from heapq import heappop, heappush

from esolangs.languages.circuit_diagram.generator.layout import _Layout


def layout_source_size(model: _Layout) -> int:
    """Return emitted characters by sweeping endpoints rather than wire cells.

    Counts keep overlapping same-column intervals live until their last end.
    """
    height, _ = model.bounds()
    if height == 0:
        return 0

    starts: dict[int, list[int]] = {}
    ends: dict[int, list[int]] = {}
    for column, runs in model.vertical.items():
        for top, bottom, _ in runs:
            # Bank block copies retain empty exclusive intervals.
            if top >= bottom:
                continue
            starts.setdefault(top, []).append(column)
            ends.setdefault(bottom, []).append(column)

    # The rightmost occupied point per row outside the verticals: a horizontal
    # run ends one cell before its exclusive bound, a junction or glyph rests
    # on its own column.
    horizontal: dict[int, int] = {}
    for row, runs in model.horizontal.items():
        horizontal[row] = max(bottom for _, bottom, _ in runs) - 1
    junctions: dict[int, int] = {}
    for x, row in model.junctions:
        junctions[row] = max(junctions.get(row, -1), x)
    glyphs: dict[int, int] = {}
    for (x, row), _ in model.glyphs.items():
        glyphs[row] = max(glyphs.get(row, -1), x)

    active: dict[int, int] = {}
    heap: list[int] = []
    size = height - 1
    for row in range(height):
        # A run's bottom row is already past it, so close first and open
        # second; a column whose runs touch there stays active throughout.
        for column in ends.get(row, ()):
            active[column] -= 1
        for column in starts.get(row, ()):
            active[column] = active.get(column, 0) + 1
            if active[column] == 1:
                heappush(heap, -column)
        while heap and active.get(-heap[0], 0) == 0:
            heappop(heap)
        edge = -heap[0] if heap else -1
        edge = max(
            edge,
            horizontal.get(row, -1),
            junctions.get(row, -1),
            glyphs.get(row, -1),
        )
        if edge >= 0:
            size += edge + 1
    return size
