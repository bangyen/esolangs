"""Raster balancing is measured on rendered, executable images."""

import itertools

import pytest

import esolangs
from esolangs.line.line_boolean import line_boolean
from esolangs.line.render import Node, render
from esolangs.line.tree_layout import tree_extents
from esolangs.piet.balance import _bounded_operations, _emit, _plan
from esolangs.raster import Raster, png

pytestmark = pytest.mark.medium

TABLES = [
    "".join(bits) for n in (1, 2) for bits in itertools.product("01", repeat=2**n)
]


def score(image: Raster) -> tuple[int, int, int]:
    width, height = len(image.rows[0]), len(image.rows)
    return abs(width - height), width * height, width


@pytest.mark.parametrize("table", [*TABLES, "10010110", "00000001", "01011010"])
def test_piet_balance_matches_rendered_width_oracle(table: str) -> None:
    operations = _bounded_operations(table)
    candidates = [esolangs.generate("Piet", table)]
    for width in range(13, sum(op.size for op in operations) + 7):
        image = esolangs.generate("Piet", table, width=width)
        assert isinstance(image, Raster)
        candidates.append(image)
        assert (
            esolangs.run(
                "Piet",
                Raster.from_png(image.to_png()),
                "0\n" * (len(table).bit_length() - 1),
            )
            == table[0]
        )
    balanced = esolangs.generate("Piet", table, balance=True)
    assert isinstance(balanced, Raster)
    assert score(balanced) == min(score(image) for image in candidates)
    assert (
        esolangs.evaluate(
            "Piet",
            Raster.from_png(balanced.to_png()),
            inputs=len(table).bit_length() - 1,
        )
        == table
    )


@pytest.mark.parametrize(
    "table",
    [
        *TABLES,
        *(
            pytest.param(table, marks=pytest.mark.slow)
            for table in ("10010110", "00000001", "01011010")
        ),
    ],
)
def test_line_balance_matches_rendered_orders(table: str) -> None:
    candidates = []
    for reverse in (False, True):
        node = line_boolean(table, reverse=reverse)
        y0, y1, x0, x1 = tree_extents(node)[id(node)]
        for heading in ((-1, 0),):
            canvas = render(node, start_heading=heading)
            assert sorted((canvas.width, canvas.height)) == sorted(
                ((x1 - x0 + 2) * 20, (y1 - y0 + 2) * 20)
            )
            candidates.append(
                (
                    abs(canvas.width - canvas.height),
                    canvas.width * canvas.height,
                    canvas.width,
                )
            )
    image = esolangs.generate("Line", table, balance=True)
    assert isinstance(image, Raster)
    assert score(image) == min(candidates)
    assert (
        esolangs.evaluate(
            "Line", Raster.from_png(image.to_png()), inputs=len(table).bit_length() - 1
        )
        == table
    )


def test_line_extent_fast_path_preserves_merged_runs_and_shared_arms() -> None:
    leaf = Node("+", next=Node("+", next=Node("o")))
    for root in (leaf, Node("?", zero=leaf, nonzero=leaf), Node("?", zero=leaf)):
        assert render(root, acyclic=True).pixels == render(root).pixels
    assert (
        esolangs.run(
            "Line",
            Raster.from_png(png.write_grey(render(leaf, acyclic=True).pixels)),
            "",
        )
        == "2"
    )
    leaf.goto = Node("o")
    with pytest.raises(ValueError, match="goto"):
        tree_extents(leaf)


def test_piet_invalid_plans_abort() -> None:
    operations = _bounded_operations("0001")
    with pytest.raises(AssertionError, match="no room"):
        _plan(operations, 5, 6)
    plan = _plan(operations, 13, 14)
    with pytest.raises(AssertionError, match="exceeds"):
        _emit(operations, plan._replace(width=1))
    overlapping = plan._replace(rows=[plan.rows[0]._replace(x=0), *plan.rows[1:]])
    with pytest.raises(AssertionError, match="overwrites"):
        _emit(operations, overlapping)
    shifted = plan._replace(
        rows=[plan.rows[0], plan.rows[1]._replace(x=plan.rows[1].x + 1), *plan.rows[2:]]
    )
    with pytest.raises(AssertionError, match="turn model"):
        _emit(operations, shifted)


def test_piet_keeps_an_already_better_layout() -> None:
    from esolangs.piet.balance import balance

    source = esolangs.generate("Piet", "0001", balance=True)
    assert isinstance(source, Raster)
    assert balance("0001", source) is source
    assert (
        esolangs.evaluate("Piet", Raster.from_png(source.to_png()), inputs=2) == "0001"
    )


def test_line_fast_path_avoids_subtree_walks(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    module = importlib.import_module("esolangs.line.render")

    def reject(*_args: object) -> None:
        raise AssertionError("tree renderer revisited a subtree")

    monkeypatch.setattr(module, "_has_goto", reject)
    monkeypatch.setattr(module, "_returns_to", reject)
    render(line_boolean("10010110"), acyclic=True)
