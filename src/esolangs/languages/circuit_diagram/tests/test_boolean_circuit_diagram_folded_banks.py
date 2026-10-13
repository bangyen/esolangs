"""Bounded folded masks with large original prefix ports."""

import importlib
from itertools import combinations, islice

import pytest

from esolangs.languages.circuit_diagram.generator import _Dag, circuit_diagram
from esolangs.languages.circuit_diagram.generator.folded_banks import (
    folded_class_bank_candidate,
)
from esolangs.languages.circuit_diagram.tests.test_boolean_circuit_diagram_pool import (
    _execute,
)


def _classes(tail, count):
    pairs = list(islice(combinations(range(1 << tail), 2), count))
    atoms = [
        "".join(str(int(row in pair)) for row in range(1 << tail)) for pair in pairs
    ]
    return "".join(atoms[row % count] for row in range(1024)), pairs


@pytest.mark.weekly
@pytest.mark.cost_evidence("public folded-mask admission beyond 256 distinct classes")
def test_public_folded_masks_share_257_classes() -> None:
    table, pairs = _classes(7, 257)
    code = circuit_diagram(table)
    lines = code.splitlines()
    assert len(lines) * max(map(len, lines)) == 8_391_063
    assert len(code) == 6_297_848
    rows = [0, 1, 127, (256 << 7) + pairs[256][0], 131071]
    assert _execute(table, code, rows) == 34


@pytest.mark.weekly
@pytest.mark.cost_evidence("eight-input atoms retain native ports beyond 512 classes")
def test_eight_input_atoms_share_513_classes() -> None:
    table, pairs = _classes(8, 513)
    model = folded_class_bank_candidate(table, 60_000_000)
    assert model is not None
    code = model.render()
    assert model.bounds()[0] * model.bounds()[1] == 34_581_525
    rows = [0, 1, 255, (512 << 8) + pairs[512][0], 262143]
    assert _execute(table, code, rows) == 24


def test_folded_masks_reject_small_ceiling_and_excess_table_work(monkeypatch) -> None:
    table, _ = _classes(7, 257)
    assert folded_class_bank_candidate(table, 100) is None
    table, _ = _classes(7, 513)
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.folded_banks"
    )

    def unexpected(*_args, **_kwargs):
        pytest.fail("excess table work must reject before folding")

    monkeypatch.setattr(module, "_dag", unexpected)
    assert folded_class_bank_candidate(table) is None


def test_unrepeated_classes_and_empty_area_reject() -> None:
    table, _ = _classes(7, 257)
    assert folded_class_bank_candidate(table, 0) is None
    assert folded_class_bank_candidate("0001") is None
    assert folded_class_bank_candidate("0" * len(table)) is None
    table, _ = _classes(7, 256)
    table = table[: 256 * 128] + "0" * (768 * 128)
    assert folded_class_bank_candidate(table) is None


def test_excess_fold_work_rejects_before_model_construction(monkeypatch) -> None:
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.folded_banks"
    )
    table, _ = _classes(7, 257)
    monkeypatch.setattr(
        module, "_dag", lambda *_args: _Dag(list(range(1000)), 0, set(), {})
    )

    def unexpected(*_args, **_kwargs):
        pytest.fail("excess fold work must reject before model construction")

    monkeypatch.setattr(module, "_circuit_diagram_model", unexpected)
    assert folded_class_bank_candidate(table) is None


def test_unavailable_body_rejects(monkeypatch) -> None:
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.folded_banks"
    )
    table, _ = _classes(7, 257)
    monkeypatch.setattr(module, "_large_pool_layout", lambda *_args, **_kwargs: None)
    assert folded_class_bank_candidate(table) is None


def test_excess_workspace_gates_reject_before_assembly(monkeypatch) -> None:
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.folded_banks"
    )
    table, _ = _classes(7, 257)

    class TooManyGates:
        glyphs = dict.fromkeys(range(2000), "a")

    monkeypatch.setattr(
        module, "_circuit_diagram_model", lambda *_args, **_kwargs: TooManyGates()
    )
    assert folded_class_bank_candidate(table) is None


def test_invalid_preflight_rectangle_aborts(monkeypatch) -> None:
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.folded_banks"
    )
    table, _ = _classes(7, 2)

    class Oversized:
        def bounds(self):
            return 10**6, 10**6

    monkeypatch.setattr(
        module, "_assemble_banks", lambda *_args, **_kwargs: Oversized()
    )
    with pytest.raises(AssertionError, match="preflight rectangle"):
        folded_class_bank_candidate(table)


@pytest.mark.slow
def test_constant_one_class_needs_only_its_mask() -> None:
    table, _ = _classes(7, 2)
    chunks = [table[i : i + 128] for i in range(0, len(table), 128)]
    first = chunks[0]
    table = "".join("1" * 128 if chunk == first else chunk for chunk in chunks)
    model = folded_class_bank_candidate(table)
    assert model is not None
    assert _execute(table, model.render(), [0, 127, 129]) <= 36


@pytest.mark.medium
def test_public_area_competition_executes_an_admitted_candidate(monkeypatch) -> None:
    module = importlib.import_module("esolangs.languages.circuit_diagram.generator")
    folded = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.folded_banks"
    )
    from tests.support.witness_tables import parity

    table = parity(9)
    model = module._circuit_diagram_model(table, None)  # noqa: SLF001
    monkeypatch.setattr(module, "_linear_shared_layout", lambda *_args: None)
    monkeypatch.setattr(folded, "folded_class_bank_candidate", lambda *_args: model)
    assert _execute(table, circuit_diagram(table)) <= 20


@pytest.mark.medium
def test_two_classes_with_large_mask_ports_execute() -> None:
    table, _ = _classes(7, 2)
    model = folded_class_bank_candidate(table)
    assert model is not None
    rows = sorted({0, len(table) - 1, *range(0, len(table), 4096)})
    assert _execute(table, model.render(), rows) <= 36


@pytest.mark.slow
def test_public_folded_masks_below_old_cap_execute_prefix_boundaries() -> None:
    table, pairs = _classes(7, 202)
    code = circuit_diagram(table)
    lines = code.splitlines()
    assert len(lines) * max(map(len, lines)) == 17_887_129
    assert len(code) == 11_578_344
    rows = sorted(
        {
            0,
            len(table) - 1,
            *(
                (prefix << 7) + row
                for prefix in (0, 1, 127, 128, 201, 202, 511, 512, 1023)
                for index in (prefix % len(pairs),)
                for row in (
                    *pairs[index],
                    next(row for row in range(128) if row not in pairs[index]),
                )
            ),
        }
    )
    assert _execute(table, code, rows) == 30


def test_the_pool_floor_is_read_through_hpool_not_snapshotted(monkeypatch) -> None:
    """A patched ``hpool`` floor must reach every bank candidate at call time.

    The candidates used to bind ``hpool._h_pool_area_floor`` at import, so a
    floor active when they first imported leaked into every later build and
    made generation depend on test order; reading through the module keeps the
    patch honest and its removal complete.
    """
    from esolangs.languages.circuit_diagram.generator.bundled_banks import (
        bundled_class_bank_candidate,
    )
    from esolangs.languages.circuit_diagram.generator.sparse_banks import (
        sparse_class_bank_candidate,
    )

    table, _ = _classes(7, 8)
    assert folded_class_bank_candidate(table) is not None
    assert sparse_class_bank_candidate(table) is not None
    assert bundled_class_bank_candidate(table) is not None
    hpool = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.hpool"
    )
    monkeypatch.setattr(hpool, "_h_pool_area_floor", lambda *_args, **_kwargs: 0)
    assert folded_class_bank_candidate(table) is None
    assert sparse_class_bank_candidate(table) is None
    assert bundled_class_bank_candidate(table) is None
