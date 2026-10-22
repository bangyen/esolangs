"""Ordered interval bookkeeping and native complete-fold controls."""

# ruff: noqa: SLF001 - the layout's indexes and interval primitive are the
# observables here.
from __future__ import annotations

from bisect import bisect_left

import pytest

from esolangs.generation.helpers import grid_area
from esolangs.languages.circuit_diagram.generator import (
    _circuit_diagram_model,
    _linear_shared_layout,
    circuit_diagram,
)
from esolangs.languages.circuit_diagram.generator.layout import _Layout
from esolangs.languages.circuit_diagram.tests.test_boolean_circuit_diagram_pool import (
    _execute,
)
from tests.support.witness_tables import dense, nested_dense


def _trace_clash(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Record how many intervals each ``_Layout._clash`` call inspects."""
    original = _Layout._clash
    inspected: list[int] = []

    def traced(runs, glyph_line, lo, hi, signal):
        hits = 0
        ordered = runs or []
        index = max(0, bisect_left(ordered, (lo, -1, -1)) - 1)
        while index < len(ordered):
            if ordered[index][0] >= hi:
                break
            hits += 1
            index += 1
        glyphs = glyph_line or []
        index = bisect_left(glyphs, lo)
        while index < len(glyphs):
            if glyphs[index] >= hi:
                break
            hits += 1
            index += 1
        inspected.append(hits)
        return original(runs, glyph_line, lo, hi, signal)

    monkeypatch.setattr(_Layout, "_clash", staticmethod(traced))
    return inspected


def _trace_glyph_columns(monkeypatch: pytest.MonkeyPatch) -> dict[int, list[int]]:
    """Record each glyph's column, in the order the Builder appends it."""
    original = _Layout.glyph
    columns: dict[int, list[int]] = {}

    def traced(self, x, y, char):
        columns.setdefault(x, []).append(y)
        original(self, x, y, char)

    monkeypatch.setattr(_Layout, "glyph", traced)
    return columns


@pytest.mark.medium
@pytest.mark.parametrize("n", [8, 9, 10, 11, 12])
def test_unbanded_builder_keeps_ordered_glyph_columns_and_short_clashes(
    monkeypatch: pytest.MonkeyPatch, n: int
) -> None:
    inspected = _trace_clash(monkeypatch)
    columns = _trace_glyph_columns(monkeypatch)
    _circuit_diagram_model(dense(n), None)
    # A column's glyphs arrive top to bottom, so the Builder appends where the
    # list already reaches; a bisect insert would mean the invariant broke.
    for ys in columns.values():
        assert ys == sorted(ys)
        assert len(set(ys)) == len(ys)
    assert inspected
    # Gate rows and each bus's reached row increase; only the predecessor
    # can intersect a new run, independently of the growing axis.
    assert max(inspected) <= 4


def test_out_of_order_insertion_is_not_a_builder_invariant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_Layout`` sorts any insertion; only the Builder guarantees the append."""
    layout = _Layout()
    original = _Layout.glyph
    inserted: list[int] = []

    def traced(self, x, y, char):
        inserted.append(bisect_left(self._glyph_cols.get(x, ()), y))
        original(self, x, y, char)

    monkeypatch.setattr(_Layout, "glyph", traced)
    layout.glyph(3, 9, "a")
    layout.glyph(3, 1, "b")
    assert layout._glyph_cols[3] == [1, 9]
    assert inserted == [0, 0]  # the out-of-order glyph lands at the front
    runs: list[tuple[int, int, int]] = []
    _Layout._record(runs, (4, 8, 1))
    _Layout._record(runs, (0, 4, 1))
    assert runs == [(0, 8, 1)]  # a backward same-signal run coalesces


@pytest.mark.medium
@pytest.mark.parametrize("n", [3, 4, 5])
def test_unbanded_complete_models_execute_every_tiny_row(n: int) -> None:
    table = dense(n)
    model = _circuit_diagram_model(table, None)
    _execute(table, model.render())


@pytest.mark.medium
def test_complete_models_execute_the_existing_repeat_control() -> None:
    table = dense(7, b"single-class-ceiling") * 4
    n = 9
    models: list[_Layout] = []
    _linear_shared_layout(table, n, models)
    assert models
    for model in models:
        _execute(table, model.render(), (0, 1, (1 << n) - 1))


@pytest.mark.medium
def test_public_uncapped_models_compete_on_area() -> None:
    table = dense(8)
    models: list[_Layout] = []
    _linear_shared_layout(table, 8, models)
    assert models
    code = circuit_diagram(table)
    assert grid_area(code) <= min(grid_area(model.render()) for model in models)
    _execute(table, code, (0, 255))


@pytest.mark.medium
@pytest.mark.parametrize("family", [dense, nested_dense])
def test_smaller_area_replaces_shorter_text(family) -> None:
    """Grids are judged by area: the area winner ships though its text is longer."""
    table = family(10)
    models: list[_Layout] = []
    _linear_shared_layout(table, 10, models)
    area_winner = min(models, key=lambda model: grid_area(model.render()))
    code = circuit_diagram(table)
    assert grid_area(code) <= grid_area(area_winner.render())
    _execute(table, code, (0, table.index("1"), len(table) - 1))
