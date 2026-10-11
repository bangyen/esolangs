"""Executed complete-cofactor banks and conservative public admission."""

import importlib

import pytest

from esolangs.tools.circuit_diagram import circuit_diagram
from esolangs.tools.circuit_diagram.banks import (
    _cofactor_bank_layout,
    _repeated_cofactor_bank,
)
from tests.support.witness_tables import dense
from tests.tools.test_boolean_circuit_diagram_pool import _execute


@pytest.mark.medium
def test_every_function_through_three_inputs_executes():
    for n in (1, 2, 3):
        for value in range(1 << (1 << n)):
            table = f"{value:0{1 << n}b}"
            _execute(table, _cofactor_bank_layout(table).render())


@pytest.mark.medium
@pytest.mark.parametrize("n", [4, 5, 6])
def test_sampled_small_banks_execute(n):
    for seed in range(4):
        table = dense(n, f"bank:{seed}".encode())
        _execute(table, _cofactor_bank_layout(table).render())


@pytest.mark.medium
@pytest.mark.parametrize("n", [8, 9])
def test_public_repeated_cofactors_share_one_body(n):
    a, b = dense(n - 2, b"bank-a"), dense(n - 2, b"bank-b")
    table = a + b + b + a
    model = _cofactor_bank_layout(table)
    code = circuit_diagram(table)
    assert code == model.render()
    assert len(code) == {8: 628_854, 9: 1_273_998}[n]
    assert sum(char in "ao~" for char in model.glyphs.values()) <= (
        2 * len(table) + 4 * n + 27
    )
    _execute(table, code)


@pytest.mark.medium
def test_unique_dense_cofactors_leave_no_bank_candidate():
    table = dense(8)
    assert _repeated_cofactor_bank(table) is None
    assert len(circuit_diagram(table)) == 1_176_281


@pytest.mark.medium
def test_oversized_bank_cannot_displace_existing_output(monkeypatch):
    table = dense(8)
    expected = circuit_diagram(table)

    class Oversized:
        def bounds(self):
            return len(expected) + 1, len(expected) + 1

        def render(self):
            pytest.fail("oversized bank must not be emitted")

    module = importlib.import_module("esolangs.tools.circuit_diagram.banks")
    monkeypatch.setattr(module, "_repeated_cofactor_bank", lambda _: Oversized())
    assert circuit_diagram(table) == expected


@pytest.mark.medium
def test_explicit_width_never_builds_a_bank(monkeypatch):
    module = importlib.import_module("esolangs.tools.circuit_diagram.banks")
    monkeypatch.setattr(
        module,
        "_repeated_cofactor_bank",
        lambda _: pytest.fail("width-constrained construction must remain independent"),
    )
    a, b = dense(6, b"bank-a"), dense(6, b"bank-b")
    table = a + b + b + a
    _execute(table, circuit_diagram(table, width=80), (0, 255))


@pytest.mark.medium
def test_equal_area_bank_preserves_existing_output(monkeypatch):
    from esolangs.tools.circuit_diagram.hpool import _h_pool_layout

    table = dense(8)
    expected = circuit_diagram(table)
    bounds = _h_pool_layout(table).bounds()

    class EqualArea:
        def bounds(self):
            return bounds

        def render(self):
            pytest.fail("area ties must preserve the existing candidate")

    module = importlib.import_module("esolangs.tools.circuit_diagram.banks")
    monkeypatch.setattr(module, "_repeated_cofactor_bank", lambda _: EqualArea())
    assert circuit_diagram(table) == expected


@pytest.mark.slow
@pytest.mark.parametrize("arities", [(8, 10, 12), (9, 11, 13)])
def test_bank_scaling_retains_native_contracts(arities):
    sizes = []
    for n in arities:
        a, b = dense(n - 2, b"bank-a"), dense(n - 2, b"bank-b")
        table = a + b + b + a
        code = _cofactor_bank_layout(table).render()
        sizes.append(len(code))
        rows = sorted({0, len(table) - 1, *range(0, len(table), len(table) // 32)})
        _execute(table, code, rows)
    assert (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) < 4.4
