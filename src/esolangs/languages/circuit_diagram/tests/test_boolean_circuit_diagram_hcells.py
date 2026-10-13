"""H cell routing preserves interval guards and emitted native behaviour."""

import random

import pytest

from esolangs.languages.circuit_diagram.generator import hlayout, hpool
from esolangs.languages.circuit_diagram.generator.hcells import _HCellLayout
from esolangs.languages.circuit_diagram.generator.hlayout import _h_term_layout
from esolangs.languages.circuit_diagram.generator.hpool import _h_pool_layout
from esolangs.languages.circuit_diagram.generator.layout import _HOLD, _RoutingLayout
from esolangs.languages.circuit_diagram.tests.test_boolean_circuit_diagram_pool import (
    _execute,
)


class _IntervalBaseline(_RoutingLayout):
    def __init__(self, _width):
        super().__init__()

    def seal(self):
        return self


@pytest.mark.medium
@pytest.mark.parametrize("n", [6, 7, 8])
@pytest.mark.parametrize("module", [hlayout, hpool])
def test_h_cell_router_preserves_emitted_bytes_and_native_contracts(
    monkeypatch, n, module
) -> None:
    rng = random.Random(813 + n)
    table = "".join(str(rng.randrange(2)) for _ in range(1 << n))
    build = _h_term_layout if module is hlayout else _h_pool_layout
    candidate = build(table).render()
    monkeypatch.setattr(module, "_HCellLayout", _IntervalBaseline)
    assert candidate == build(table).render()
    _execute(table, candidate)


@pytest.mark.parametrize("shape", ["down", "across", "under"])
@pytest.mark.parametrize(
    "obstacle", ["glyph", "junction", "reserved", "hold", "parallel"]
)
def test_h_cell_routes_reject_foreign_obstacles(shape, obstacle) -> None:
    layout = _HCellLayout(32)
    # All shapes include the source endpoint; holds also guard neighbours.
    if obstacle == "glyph":
        layout.glyph(8, 8, "a")
    elif obstacle == "junction":
        layout.junction(8, 8, 2)
    elif obstacle == "reserved":
        layout.reserve((8, 8), 2)
    elif obstacle == "hold":
        layout.reserve((9, 9), _HOLD)
    else:
        layout.run_horizontal(6, 10, 8, 2)
    with pytest.raises(AssertionError, match="collides"):
        layout.route((8, 8), (16, 16), 1, shape)


def test_h_cell_sealing_preserves_gaps_and_legitimate_crossings() -> None:
    layout = _HCellLayout(32)
    layout.run_horizontal(18, 24, 8, 1)
    layout.run_horizontal(2, 6, 8, 1)
    layout.run_horizontal(5, 8, 8, 1)
    layout.run_vertical(4, 2, 12, 2)
    layout.glyph(1, 14, ":")
    layout.glyph(3, 14, "a")
    result = layout.seal()
    assert result.horizontal[8] == [(3, 8, 1), (19, 24, 1)]
    assert result.render() == layout.render()
    assert result.render().splitlines()[8][4] == "="
    assert result._glyph_rows[14] == [1, 3]  # noqa: SLF001
    assert result._glyph_cols[1] == [14]  # noqa: SLF001


@pytest.mark.parametrize("point", [(-1, 0), (32, 0), (0, -1)])
def test_h_cell_packing_rejects_out_of_bounds_coordinates(point) -> None:
    with pytest.raises(AssertionError, match="outside"):
        _HCellLayout(32).junction(*point, 1)


def test_h_cell_neighbours_do_not_wrap_across_rows() -> None:
    layout = _HCellLayout(16)
    layout.junction(15, 4, 2)
    layout.route((0, 5), (0, 8), 1)
    assert layout.junctions[0, 5] == 1
