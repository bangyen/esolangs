"""Executed four-root bundles and bounded mask work."""

import importlib

import pytest

from esolangs.languages.circuit_diagram.generator import _Dag, circuit_diagram
from esolangs.languages.circuit_diagram.generator.bundled_banks import (
    bundled_class_bank_candidate,
)
from esolangs.languages.circuit_diagram.generator.forest import _suffix_forest
from esolangs.languages.circuit_diagram.generator.layout import _layout_area
from esolangs.languages.circuit_diagram.tests.test_boolean_circuit_diagram_pool import (
    _execute,
)
from tests.support.witness_tables import dense, nested_dense, parity


@pytest.mark.medium
@pytest.mark.parametrize("family", [dense, nested_dense])
@pytest.mark.parametrize("n", [9, 10, 11, 12])
def test_bundled_roots_execute_original_ports(family, n) -> None:
    table = family(n)
    model = bundled_class_bank_candidate(table)
    assert model is not None
    rows = sorted({0, len(table) - 1, *range(0, len(table), len(table) // 16)})
    _execute(table, model.render(), rows)


@pytest.mark.medium
@pytest.mark.parametrize("classes", [1, 2, 3, 4, 5, 7, 8, 9])
def test_bundle_boundary_and_constant_one_root_execute(classes) -> None:
    atoms = [dense(7, f"bundle:{i}".encode()) for i in range(classes - 1)]
    atoms.append("1" * 128)
    table = "".join(atoms[row % classes] if row % 5 else "0" * 128 for row in range(16))
    model = bundled_class_bank_candidate(table)
    assert model is not None
    rows = sorted(
        {
            0,
            len(table) - 1,
            *(prefix * 128 + suffix for prefix in range(16) for suffix in (0, 63, 127)),
        }
    )
    _execute(table, model.render(), rows)


def test_bundle_rejects_constants_small_prefixes_and_zero_budget() -> None:
    assert bundled_class_bank_candidate("0" * 512) is None
    assert bundled_class_bank_candidate("1" * 512) is None
    assert bundled_class_bank_candidate(dense(8)) is None
    assert bundled_class_bank_candidate(dense(9), 0) is None


def test_bundle_ceiling_admits_its_own_area_and_rejects_one_less() -> None:
    table = dense(9)
    model = bundled_class_bank_candidate(table)
    assert model is not None
    area = _layout_area(model)
    assert bundled_class_bank_candidate(table, area) is not None
    assert bundled_class_bank_candidate(table, area - 1) is None


def test_mask_work_is_checked_before_building_forests(monkeypatch) -> None:
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.bundled_banks"
    )
    masks = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.folded_banks"
    )
    monkeypatch.setattr(masks, "_dag", lambda *_args: _Dag([None] * 1000, 0, set(), {}))
    monkeypatch.setattr(
        module, "_suffix_forest", lambda *_args: pytest.fail("mask work rejected")
    )
    assert bundled_class_bank_candidate(dense(9)) is None


def test_excess_class_work_rejects_before_mask_extraction(monkeypatch) -> None:
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.bundled_banks"
    )
    monkeypatch.setattr(
        module, "_folded_class_masks", lambda *_args: pytest.fail("class work rejected")
    )
    assert bundled_class_bank_candidate(dense(17)) is None


def test_small_ceiling_rejects_before_copying_banks(monkeypatch) -> None:
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.bundled_banks"
    )
    monkeypatch.setattr(
        module,
        "_assemble_banks",
        lambda *_args, **_kwargs: pytest.fail("area rejected"),
    )
    assert bundled_class_bank_candidate(dense(9), 1) is None


def test_gate_budget_rejects_before_copying_banks(monkeypatch) -> None:
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.bundled_banks"
    )

    def oversized(words, inputs):
        model, endpoints = _suffix_forest(words, inputs)
        model.glyphs.update({(10000 + i, 10000): "o" for i in range(1024)})
        return model, endpoints

    monkeypatch.setattr(module, "_suffix_forest", oversized)
    monkeypatch.setattr(
        module,
        "_assemble_banks",
        lambda *_args, **_kwargs: pytest.fail("gates rejected"),
    )
    assert bundled_class_bank_candidate(dense(9)) is None


@pytest.mark.medium
@pytest.mark.parametrize("extra_area", [0, 1])
def test_public_selection_preserves_existing_area_ties(monkeypatch, extra_area) -> None:
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.bundled_banks"
    )
    table = parity(9)
    original = circuit_diagram(table)

    class Unselected:
        def __init__(self, area):
            self.area = area

        def bounds(self):
            return 1, self.area

        def render(self):
            pytest.fail("existing area winner must be retained")

    monkeypatch.setattr(
        module,
        "bundled_class_bank_candidate",
        lambda _table, ceiling: Unselected(ceiling + extra_area),
    )
    code = circuit_diagram(table)
    assert code == original
    _execute(table, code, (0, 511))


@pytest.mark.medium
@pytest.mark.parametrize("tail", [7, 8])
def test_large_original_prefix_ports_execute(tail) -> None:
    atoms = [dense(tail, f"prefix-bundle:{i}".encode()) for i in range(2)]
    table = "".join(atoms[(row >> 9) ^ (row & 1)] for row in range(1024))
    model = bundled_class_bank_candidate(table)
    assert model is not None
    rows = sorted(
        {
            0,
            len(table) - 1,
            *(
                (prefix << tail) + atoms[(prefix >> 9) ^ (prefix & 1)].index(bit)
                for prefix in (0, 1, 511, 512, 1023)
                for bit in "01"
            ),
        }
    )
    _execute(table, model.render(), rows)
