"""Malformed images and obstructed returns abort before interpretation."""

import pytest

from esolangs.interpreters.tape_based.line import extract
from esolangs.interpreters.tape_based.line.mask import Mask
from esolangs.tools.line import render
from esolangs.tools.line.bf_to_line import bf_to_line


def test_thick_square_is_not_an_arrowhead() -> None:
    square = Mask(12, 12, [(1 << 12) - 1] * 12)
    with pytest.raises(ValueError, match=r"cursor|arrowhead"):
        extract.find_cursor(square)


def test_arrowhead_without_a_path_is_refused() -> None:
    square = Mask(12, 12, [(1 << 12) - 1] * 12)
    cursor = extract.Cursor(6, 6, square)
    with pytest.raises(ValueError, match="no path pixels"):
        extract.extract_tree(square, cursor)


def test_stray_specks_outside_the_cursor_are_not_a_path() -> None:
    """Ink made only of tip-sized specks leaves no path to follow."""
    rows = [0, 1 << 1, 0, 0, 0, 1 << 5, 0, 0]
    cursor = extract.Cursor(0, 0, Mask(8, 8))
    with pytest.raises(ValueError, match="no path pixels"):
        extract.extract_tree(Mask(8, 8, rows), cursor)


def test_trailing_noise_does_not_complete_a_kink() -> None:
    vertices = [
        extract.Vertex(0, 0, 0),
        extract.Vertex(-20, 0, 1),
        extract.Vertex(-40, 20, 2),
        extract.Vertex(-40, 21, None),
    ]
    assert extract.classify_ops(vertices, unit=20) == []


@pytest.mark.parametrize(
    ("spacing", "x", "possible"),
    [(5, 1, False), (20, 0, False), (20, 1, True), (20, -1, True)],
)
def test_return_bay_clearance_and_body_axis(spacing, x, possible, monkeypatch):
    target = render.Node("?", nonzero=render.Node("o"))
    monkeypatch.setattr(render, "_subtree_extent", lambda _node: (0, 10, -2, 2))
    monkeypatch.setattr(render, "_arm_spacing", lambda _node: spacing)
    # In the body's frame this is the near edge (y=0), strictly between its sides.
    legs = render._loop_return_legs(  # noqa: SLF001 - routing premises under test
        (-x, spacing), target, {id(target): ((0, 0), (1, 0))}
    )
    assert (legs is not None) is possible


def test_return_that_crosses_body_ink_is_refused(monkeypatch):
    # The body's final stroke heads west: an eastward return retraces its ink.
    monkeypatch.setattr(render, "_loop_return_legs", lambda *_args: [((0, 1), 2)])
    with pytest.raises(ValueError, match="could not be constructed"):
        render.render(bf_to_line("+[.-]"))


def test_empty_graph_is_refused() -> None:
    with pytest.raises(ValueError, match="empty path"):
        render.render(None)  # type: ignore[arg-type]


def test_canvas_clips_outside_strokes_and_polygon_fills() -> None:
    canvas = render.Canvas(3, 3)
    canvas.line([(-2, -2), (2, 2)])
    assert [canvas.pixels[i][i] for i in range(3)] == [0, 0, 0]
    canvas.polygon([(-5, 0), (-4, 0), (-4, 2)])
    assert [canvas.pixels[i][i] for i in range(3)] == [0, 0, 0]
