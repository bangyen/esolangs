"""Bounded multi-output suffix folds with a live gate-group width reserve."""

from __future__ import annotations

from esolangs.generation.helpers import _validate_truth_table

from . import _Builder, _dag, _emit_dag
from .layout import _Layout

type _Forest = tuple[_Layout, list[tuple[int, int] | None]]


class _ForestBuilder(_Builder):
    def outputs(self, sources: list[int | None]) -> list[tuple[int, int] | None]:
        """Export roots on fresh footer rows; constant one needs no suffix."""
        column = max(self.next_column, max(x for x, _ in self.buses.values()) + 4) + 4
        endpoints: list[tuple[int, int] | None] = []
        for signal in sources:
            if signal is None:
                endpoints.append(None)
                continue
            row = self._new_band()
            self._tap(signal, column, row)
            self.layout.glyph(column + 1, row, "-")
            self.layout.glyph(column + 2, row, ":")
            endpoints.append((column, row))
        return endpoints


def _suffix_forest(words: list[str], inputs: int) -> _Forest:
    """Fold nonzero classes within their Boolean capacity, through eight inputs."""
    if not 1 <= inputs <= 8 or not 1 <= len(words) < 1 << (1 << inputs):
        raise ValueError("suffix forests exceed their input or class capacity")
    for word in words:
        if _validate_truth_table(word) != inputs or "1" not in word:
            raise ValueError("suffix classes must be nonzero tables of the same arity")
    if not any("0" in word for word in words):
        raise ValueError("suffix forests need a nonconstant class")
    size = 1 << (len(words) - 1).bit_length()
    virtual = size.bit_length() - 1
    dag = _dag("".join(words + [words[-1]] * (size - len(words))), inputs + virtual)
    by_id = {node: (level, zero, one) for level, zero, one, node in dag[0]}
    roots = []
    for index in range(len(words)):
        root = dag[1]
        for bit in range(virtual - 1, -1, -1):
            if root in by_id and by_id[root][0] == inputs + bit:
                root = by_id[root][2 if (index >> bit) & 1 else 1]
        roots.append(root)
    ops = [op for op in dag[0] if op[0] < inputs]
    needed = {
        inputs - 1 - level for level, zero, one, _ in ops if zero != 0 and one != 1
    }
    reads: dict[int, int] = {}
    for _, zero, one, _ in ops:
        for child in (zero, one):
            if child > 1:
                reads[child] = reads.get(child, 0) + 1
    for root in roots:
        if root > 1:
            reads[root] = reads.get(root, 0) + 1
    producing = {
        node for _, zero, one, node in ops if (zero, one) not in ((0, 1), (1, 0))
    }
    remaining = reads.copy()
    live: set[int] = set()
    peak = 0
    for _, zero, one, node in ops:
        if node not in producing:
            continue
        # A full mux briefly holds its two AND results and its OR result.
        peak = max(peak, len(live) + 3)
        for child in (zero, one):
            if child in producing:
                remaining[child] -= 1
                if remaining[child] == 0:
                    live.remove(child)
        live.add(node)
    builder = _ForestBuilder(narrow=True)
    rails = [builder.input_bus() for _ in range(inputs)]
    selectors: list[list[int | None]] = [
        [rail, builder.invert(rail) if index in needed else None]
        for index, rail in enumerate(rails)
    ]
    builder.band_start = builder.next_column
    # Reserve one four-column gate group per live result. A fixed 128-column
    # cap forced repeated carries: the eight-root n=14 probe timed out at 30s.
    builder.limit = builder.band_start + 4 * peak + 8
    values = _emit_dag(builder, selectors, (ops, dag[1], needed, reads))
    sources: list[int | None] = []
    for root in roots:
        if root == 1:
            sources.append(None)
        else:
            source = values[root]
            if not isinstance(source, int):
                raise AssertionError("nonconstant forest root has no signal")
            sources.append(source)
    return builder.layout, builder.outputs(sources)
