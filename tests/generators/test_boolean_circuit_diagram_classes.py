"""Native bounded suffix-class banks across arbitrary prefix occurrences."""

import importlib

import pytest

from esolangs.tools.circuit_diagram import _linear_shared_layout, circuit_diagram
from esolangs.tools.circuit_diagram.banks import (
    _repeated_cofactor_bank,
    _residual_class_bank_candidate,
)
from tests.support.witness_tables import dense
from tests.tools.test_boolean_circuit_diagram_pool import _execute


def _three_classes(n):
    tail = 7 if n % 2 else 8
    atoms = [dense(tail, f"class:{i}".encode()) for i in range(3)]
    selector = dense(n - tail, b"class-selector")
    return "".join(
        atoms[(2 * int(bit) + row % 2) % 3] for row, bit in enumerate(selector)
    )


def _eight_classes(n):
    tail = 7 if n % 2 else 8
    prefix = n - tail
    atoms = [dense(tail, f"eight-class:{i}".encode()) for i in range(8)]
    selectors = [dense(prefix, f"class-bit:{i}".encode()) for i in range(3)]
    return "".join(
        atoms[sum(int(selectors[bit][row]) << bit for bit in range(3))]
        for row in range(1 << prefix)
    )


@pytest.mark.medium
@pytest.mark.parametrize("n", [9, 10])
def test_repeated_classes_execute_every_row(n):
    table = _three_classes(n)
    model = _residual_class_bank_candidate(table)
    assert model is not None
    assert len(model.render()) == {9: 122_190, 10: 251_574}[n]
    _execute(table, model.render())


@pytest.mark.medium
def test_public_abba_class_bank_executes_every_row():
    a, b = dense(8, b"bank-a"), dense(8, b"bank-b")
    table = a + b + b + a
    code = circuit_diagram(table)
    lines = code.splitlines()
    assert len(lines) * max(map(len, lines)) == 389_994
    _execute(table, code)


@pytest.mark.medium
def test_classes_cross_distinct_banks_beyond_all_fold_orders():
    table = _eight_classes(13)
    assert _linear_shared_layout(table, 13) is None
    assert _repeated_cofactor_bank(table) is None
    chunks = [table[start : start + 1024] for start in range(0, len(table), 1024)]
    assert len(set(chunks)) == 8
    code = circuit_diagram(table)
    assert code == _residual_class_bank_candidate(table).render()
    lines = code.splitlines()
    assert len(lines) * max(map(len, lines)) == 1_251_332
    rows = sorted({0, len(table) - 1, *range(0, len(table), 256)})
    _execute(table, code, rows)


@pytest.mark.medium
def test_constant_classes_and_projected_suffix_ports_execute():
    atom = "".join(str(((row >> 6) & 1) ^ (row & 1)) for row in range(128))
    for table in ("0" * 128 + "1" * 128 + atom + atom, atom * 4):
        model = _residual_class_bank_candidate(table)
        assert model is not None
        _execute(table, model.render())


def test_unrepeated_and_excess_classes_reject_before_routing(monkeypatch):
    module = importlib.import_module("esolangs.tools.circuit_diagram.banks")

    def unexpected(*_args, **_kwargs):
        pytest.fail("ineligible classes must be rejected before building masks")

    monkeypatch.setattr(module, "_large_pool_layout", unexpected)
    assert _residual_class_bank_candidate(dense(10)) is None
    atoms = [dense(7, f"too-many:{i}".encode()) for i in range(129)]
    assert (
        _residual_class_bank_candidate("".join(atoms[row % 129] for row in range(256)))
        is None
    )
    assert _residual_class_bank_candidate("0" * 512) is None
    assert _residual_class_bank_candidate(dense(8)) is None


@pytest.mark.medium
def test_class_area_ceiling_preserves_a_fitting_native_layout(monkeypatch):
    table = _three_classes(9)
    model = _residual_class_bank_candidate(table)
    height, width = model.bounds()
    assert (
        _residual_class_bank_candidate(table, height * width).render() == model.render()
    )
    assert _residual_class_bank_candidate(table, height * width - 1) is None
    _execute(table, model.render(), (0, len(table) - 1))
    module = importlib.import_module("esolangs.tools.circuit_diagram.banks")

    def unexpected(*_args, **_kwargs):
        pytest.fail("an oversized body must reject before copying banks")

    monkeypatch.setattr(module, "_assemble_banks", unexpected)
    assert _residual_class_bank_candidate(table, 1) is None


@pytest.mark.medium
@pytest.mark.parametrize("extra_height", [0, 1])
def test_public_class_admission_preserves_existing_area_ties(monkeypatch, extra_height):
    module = importlib.import_module("esolangs.tools.circuit_diagram.banks")
    monkeypatch.setattr(module, "_cofactor_bank_candidate", lambda *_args: None)
    monkeypatch.setattr(module, "_residual_class_bank_candidate", lambda *_args: None)
    table = dense(9)
    expected = circuit_diagram(table)
    lines = expected.splitlines()

    class Rejected:
        def bounds(self):
            return len(lines) + extra_height, max(map(len, lines))

        def render(self):
            pytest.fail("an equal or larger class bank must preserve the old candidate")

    monkeypatch.setattr(
        module, "_residual_class_bank_candidate", lambda *_args: Rejected()
    )
    assert circuit_diagram(table) == expected
    _execute(table, expected, (0, len(table) - 1))


@pytest.mark.medium
def test_explicit_width_never_builds_class_masks(monkeypatch):
    module = importlib.import_module("esolangs.tools.circuit_diagram.banks")

    def unexpected(*_args, **_kwargs):
        pytest.fail("class masks must not run in the width-constrained fold")

    monkeypatch.setattr(module, "_residual_class_bank_candidate", unexpected)
    table = _three_classes(9)
    _execute(table, circuit_diagram(table, width=80), (0, len(table) - 1))


@pytest.mark.slow
@pytest.mark.parametrize("arities", [(9, 11, 13), (10, 12, 14)])
def test_class_bank_growth_executes_native_positive_controls(arities):
    sizes = []
    for n in arities:
        table = _three_classes(n)
        model = _residual_class_bank_candidate(table)
        assert model is not None
        code = model.render()
        rows = sorted({0, len(table) - 1, *range(0, len(table), len(table) // 32)})
        _execute(table, code, rows)
        sizes.append(len(code))
    assert (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) <= 4.4


@pytest.mark.slow
def test_large_h_masks_keep_their_local_complement_drivers():
    table = _three_classes(17)
    model = _residual_class_bank_candidate(table)
    assert model is not None
    rows = sorted({0, len(table) - 1, *range(0, len(table), len(table) // 32)})
    _execute(table, model.render(), rows)
