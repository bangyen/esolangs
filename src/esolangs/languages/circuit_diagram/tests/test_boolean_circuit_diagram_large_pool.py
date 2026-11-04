"""Native controls for bounded larger atoms and routing area floors."""

import importlib
import re
from pathlib import Path

import pytest

from esolangs.languages.circuit_diagram.generator import circuit_diagram
from esolangs.languages.circuit_diagram.generator.hpool import (
    _atom_gate_bound,
    _large_pool_layout,
)
from esolangs.languages.circuit_diagram.tests.test_boolean_circuit_diagram_pool import (
    _execute,
)
from tests.support.witness_tables import dense, nested_dense, parity


@pytest.mark.medium
@pytest.mark.parametrize("n", [9, 10, 11])
def test_large_pool_area_is_table_independent_and_fits_its_floor(n) -> None:
    """Bank budgets rely on the pool area being a function of (n, ports) only."""
    dense_model = _large_pool_layout(dense(n))
    parity_model = _large_pool_layout(parity(n))
    assert dense_model.bounds() == parity_model.bounds()
    height, width = dense_model.bounds()
    assert _large_pool_layout(dense(n), ceiling=height * width) is not None
    assert _large_pool_layout(dense(n), ceiling=height) is None


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

    table = dense(9)
    model = _large_pool_layout(table)
    assert model is not None
    _execute(table, model.render(), (0, 1, 511))
    calls = []

    def routed(*_args, **_kwargs):
        calls.append(True)
        return model

    monkeypatch.setattr(module, "_pool_layout", routed)
    assert _large_pool_layout(table, ceiling=1) is None
    # The retained n=9 leaf-AND floor is 1,142,625 cells. Probe its boundary,
    # not just a tiny ceiling: a weakened margin used to pass the latter.
    assert _large_pool_layout(table, ceiling=1_142_624) is None
    assert not calls
    with pytest.raises(ValueError, match="distinct original ports"):
        _large_pool_layout(table, input_order=[0] * 9, ceiling=1)
    assert _large_pool_layout(table, ceiling=1_142_625) is None
    assert calls  # positive control: equal floor admits routing before final rejection


@pytest.mark.medium
def test_direct_atom_exact_area_ceiling(monkeypatch) -> None:
    table = dense(8)
    model = _large_pool_layout(table)
    assert model is not None
    height, width = model.bounds()
    assert _large_pool_layout(table, ceiling=height * width) is not None
    assert _large_pool_layout(table, ceiling=height * width - 1) is None
    _execute(table, model.render(), (0, len(table) - 1))
    from esolangs.languages.circuit_diagram.generator.hpool import _PoolBuild

    build = _PoolBuild(dense(9), 7, list(range(9)), 9, {})
    side = build.geometry.leaf_height - 8 * build.k - 48
    monkeypatch.setattr(model, "bounds", lambda: (side, side))
    build._check_fits(model)
    for h, w in ((side + 1, side), (side, side + 1)):
        monkeypatch.setattr(model, "bounds", lambda h=h, w=w: (h, w))
        with pytest.raises(AssertionError, match="exceeded its rectangle"):
            build._check_fits(model)


@pytest.mark.medium
def test_large_pool_is_the_competing_model_when_folds_decline(monkeypatch) -> None:
    module = importlib.import_module("esolangs.languages.circuit_diagram.generator")
    monkeypatch.setattr(module, "_linear_shared_layout", lambda *_args: None)
    table = dense(8)
    code = circuit_diagram(table)
    assert code == _large_pool_layout(table).render()
    _execute(table, code)


def test_compete_binds_no_patched_name() -> None:
    """compete is imported lazily: a name bound there misses later patches.

    Its first import inside a patch also kept the patch: a zero pool floor
    made every later build route the H pool, 2.3 s -> 6.2 s.
    """
    patched = {
        name
        for path in Path(__file__).parent.glob("test_*.py")
        for name in re.findall(r'setattr\(\s*\w+,\s*"(\w+)"', path.read_text())
    }
    compete = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.compete"
    )
    assert not patched & set(vars(compete))


@pytest.mark.slow
@pytest.mark.parametrize(
    ("family", "arities", "caps"),
    [
        (dense, (8, 10, 12), (52_057, 287_892, 2_667_702)),
        (dense, (9, 11, 13), (106_751, 845_725, 6_095_641)),
        (nested_dense, (8, 10, 12), (46_723, 271_684, 2_913_235)),
    ],
)
def test_public_growth_executes_positive_controls(family, arities, caps) -> None:
    # Independent rung caps catch growth without penalizing a smaller early
    # fold when the larger rung still selects a primitive layout.
    for n, cap in zip(arities, caps, strict=True):
        table = family(n)
        code = circuit_diagram(table)
        rows = sorted({0, len(table) - 1, *range(0, len(table), len(table) // 32)})
        _execute(table, code, rows)
        assert len(code) <= cap, n


def test_large_pool_parks_an_ignored_input_port() -> None:
    table = dense(9)
    model = _large_pool_layout(table, input_order=list(range(9)), port_inputs=10)
    assert model is not None
    # The tenth port is read and dropped: each row's bit holds for both of its values.
    full = "".join(table[row >> 1] for row in range(1 << 10))
    _execute(full, model.render(), [0, 1, 2, 511, 512, 1022, 1023])
