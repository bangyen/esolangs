"""Native controls for bounded larger atoms and routing area floors."""

import importlib

import pytest

from esolangs.languages.circuit_diagram.generator import circuit_diagram
from esolangs.languages.circuit_diagram.generator.hlayout import (
    _h_term_area_floor,
    _h_term_layout,
)
from esolangs.languages.circuit_diagram.generator.hpool import (
    _atom_gate_bound,
    _h_pool_area_floor,
    _h_pool_layout,
    _large_pool_layout,
)
from esolangs.languages.circuit_diagram.tests.test_boolean_circuit_diagram_pool import (
    _execute,
)
from tests.support.witness_tables import dense, nested_dense, parity


@pytest.mark.medium
@pytest.mark.parametrize("n", [6, 7, 8])
def test_retained_glyph_floors_bound_executed_layouts(n) -> None:
    table = dense(n)
    for build, floor in (
        (_h_term_layout, _h_term_area_floor),
        (_h_pool_layout, _h_pool_area_floor),
    ):
        model = build(table)
        height, width = model.bounds()
        assert 0 < floor(n, n) <= height * width
        _execute(table, model.render(), (0, 1, (1 << n) - 1))


@pytest.mark.medium
@pytest.mark.parametrize("n", [7, 8])
def test_direct_large_atoms_execute_every_row(n) -> None:
    table = dense(n)
    model = _large_pool_layout(table)
    assert model is not None
    assert _atom_gate_bound(n) == {7: 114, 8: 211}[n]
    _execute(table, model.render())


@pytest.mark.medium
def test_large_pool_routes_mixed_constant_and_shared_atoms() -> None:
    atom = dense(7)
    table = "0" * 128 + "1" * 128 + parity(7) + atom
    model = _large_pool_layout(table)
    assert model is not None
    _execute(table, model.render())


@pytest.mark.medium
def test_large_atom_preserves_gapped_original_ports() -> None:
    atom = dense(7)
    order = [0, 1, 2, 3, 4, 6, 7]
    table = "".join(
        atom[int("".join(f"{row:08b}"[port] for port in order), 2)]
        for row in range(256)
    )
    model = _large_pool_layout(atom, input_order=order, port_inputs=8)
    assert model is not None
    _execute(table, model.render())


def test_large_pool_floor_rejects_before_atom_routing(monkeypatch) -> None:
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.hpool"
    )

    def unexpected(*_args, **_kwargs):
        pytest.fail("area floor must reject before routing atoms")

    monkeypatch.setattr(module, "_pool_layout", unexpected)
    assert _large_pool_layout(dense(9), ceiling=1) is None
    with pytest.raises(ValueError, match="distinct original ports"):
        _large_pool_layout(dense(9), input_order=[0] * 9, ceiling=1)


def test_area_floors_without_retained_terms_are_zero() -> None:
    assert _h_term_area_floor(1, 8) == 0
    assert _h_pool_area_floor(4, 8) == 0


@pytest.mark.medium
def test_direct_atom_exact_area_ceiling() -> None:
    table = dense(8)
    model = _large_pool_layout(table)
    assert model is not None
    height, width = model.bounds()
    assert _large_pool_layout(table, ceiling=height * width) is not None
    assert _large_pool_layout(table, ceiling=height * width - 1) is None


@pytest.mark.medium
@pytest.mark.parametrize("floor", [0, 10**12])
def test_large_atom_displaces_older_layout_after_exact_comparison(
    monkeypatch, floor
) -> None:
    module = importlib.import_module("esolangs.languages.circuit_diagram.generator")
    monkeypatch.setattr(module, "_linear_shared_layout", lambda *_args: None)
    monkeypatch.setattr(module, "_h_term_area_floor", lambda *_args: floor)
    pools = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.hpool"
    )
    monkeypatch.setattr(pools, "_h_pool_area_floor", lambda *_args: 0)
    table = dense(8)
    code = circuit_diagram(table)
    assert code == _large_pool_layout(table).render()
    _execute(table, code)


@pytest.mark.slow
@pytest.mark.parametrize(
    ("family", "arities"),
    [(dense, (8, 10, 12)), (dense, (9, 11, 13)), (nested_dense, (8, 10, 12))],
)
def test_public_growth_executes_positive_controls(family, arities) -> None:
    sizes = []
    for n in arities:
        table = family(n)
        code = circuit_diagram(table)
        rows = sorted({0, len(table) - 1, *range(0, len(table), len(table) // 32)})
        _execute(table, code, rows)
        sizes.append(len(code))
    assert 0 < sizes[2] - sizes[1] <= 4.4 * (sizes[1] - sizes[0])
