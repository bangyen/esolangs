"""Exact source-size counts against rendered Circuit Diagram layouts."""

from __future__ import annotations

import pytest

from esolangs.languages.circuit_diagram.generator import _circuit_diagram_model
from esolangs.languages.circuit_diagram.generator.layout import _Layout
from esolangs.languages.circuit_diagram.generator.source_size import layout_source_size
from tests.support.witness_tables import dense, parity


@pytest.mark.parametrize(
    "table",
    [
        dense(2),
        dense(3),
        dense(4),
        parity(2),
        parity(3),
        parity(4),
        "00",
        "11",
        "0000",
        "1111",
    ],
)
def test_unbanded_builder_size_matches_render(table: str) -> None:
    """A real unbanded Builder model counts exactly what it renders."""
    model = _circuit_diagram_model(table, None)
    assert layout_source_size(model) == len(model.render())


def test_manual_runs_with_empty_rows_and_a_lone_glyph_match_render() -> None:
    """Touch two same-column runs across a gap, then a glyph-only last row."""
    layout = _Layout()
    layout.run_vertical(3, 1, 5, 1)  # column 3 on rows 2..4
    layout.run_vertical(3, 5, 9, 2)  # column 3 again on rows 6..8
    layout.run_vertical(1, 3, 9, 3)  # column 1 on rows 4..8
    layout.glyph(6, 12, ":")  # rows 9..11 stay empty
    assert layout_source_size(layout) == len(layout.render())


def test_overlapping_runs_in_one_column_stay_active_to_the_last() -> None:
    """The count keeps a shared column active past the first run's end."""
    layout = _Layout()
    # run_vertical refuses overlapping other signals, so the two runs are
    # written directly to exercise the sweep's count.
    layout.vertical[4] = [(2, 6, 1), (4, 9, 2)]
    layout.glyph(4, 1, "-")
    assert layout_source_size(layout) == len(layout.render())


def test_empty_exclusive_intervals_from_bank_copies_match_render() -> None:
    layout = _Layout()
    layout.vertical[4] = [(2, 2, 1), (5, 4, 1), (6, 9, 1)]
    layout.glyph(1, 10, ":")
    assert layout_source_size(layout) == len(layout.render())


def test_giant_vertical_run_is_counted_without_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One interval of many rows costs O(rows) only as the sweep's height."""
    layout = _Layout()
    depth = 1 << 14
    layout.run_vertical(7, 1, depth, 1)
    layout.junction(7, 1, 1)
    layout.junction(7, depth, 1)

    def refuse(*_args: object, **_kwargs: object) -> str:
        pytest.fail("layout_source_size must not render the layout")

    monkeypatch.setattr(_Layout, "render", refuse)
    # Row 0 is empty; rows 1..depth each hold column 7, and the join adds
    # height - 1 = depth newlines.
    assert layout_source_size(layout) == 9 * depth


def test_giant_horizontal_run_is_counted_without_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run's own length never enters the count, only its endpoints."""
    layout = _Layout()
    width = 1 << 20
    layout.run_horizontal(1, width, 3, 1)
    layout.junction(1, 3, 1)
    layout.junction(width, 3, 1)

    def refuse(*_args: object, **_kwargs: object) -> str:
        pytest.fail("layout_source_size must not paint the run")

    monkeypatch.setattr(_Layout, "render", refuse)
    # Height stays four rows however long the run is; only its right end and
    # three empty rows above it contribute.
    assert layout_source_size(layout) == width + 4


def test_empty_layout_has_no_source() -> None:
    layout = _Layout()
    assert layout_source_size(layout) == len(layout.render()) == 0
