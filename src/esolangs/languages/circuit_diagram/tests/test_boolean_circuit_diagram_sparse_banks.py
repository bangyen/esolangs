"""Executed occurrence-mask banks beyond the dense-mask work cutoff."""

import importlib
from itertools import combinations

import pytest

from esolangs.languages.circuit_diagram.generator import _dag, circuit_diagram
from esolangs.languages.circuit_diagram.generator.sparse_banks import (
    sparse_class_bank_candidate,
)
from esolangs.languages.circuit_diagram.tests.test_boolean_circuit_diagram_pool import (
    _execute,
)
from tests.support.witness_tables import dense


def _two_classes():
    atoms = [dense(7, b"sparse-bank-ports"), "1" * 128]
    return "".join(
        atoms[(row >> 9) ^ (row & 1)] if row & 2 else "0" * 128 for row in range(1024)
    )


def _spread_pairs(count):
    pairs = list(combinations(range(128), 2))
    chosen = [pairs[(8191 * i + 4093) % len(pairs)] for i in range(count)]
    atoms = ["".join(str(int(row in pair)) for row in range(128)) for pair in chosen]
    return atoms, chosen


@pytest.mark.medium
def test_sparse_banks_keep_constant_classes_ignored_inputs_and_original_ports() -> None:
    table = _two_classes()
    model = sparse_class_bank_candidate(table)
    assert model is not None
    rows = sorted(
        {
            0,
            len(table) - 1,
            *(p * 128 + s for p in (0, 3, 511, 512, 1023) for s in (0, 63, 127)),
        }
    )
    _execute(table, model.render(), rows)


def test_sparse_banks_reject_limits_before_copying(monkeypatch) -> None:
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.sparse_banks"
    )

    def unexpected(*_args, **_kwargs):
        pytest.fail("rejected banks must not be copied")

    monkeypatch.setattr(module, "_assemble_banks", unexpected)
    assert sparse_class_bank_candidate(_two_classes(), 1) is None
    assert sparse_class_bank_candidate("0" * 131072) is None
    assert sparse_class_bank_candidate(dense(8)) is None
    assert sparse_class_bank_candidate(dense(7) * 1024) is None
    work_type = module._SparseWork  # noqa: SLF001
    monkeypatch.setattr(module, "_SparseWork", lambda _limit: work_type(0))
    assert sparse_class_bank_candidate(_two_classes()) is None


def test_clock_bound_rejects_before_mask_folding(monkeypatch) -> None:
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.sparse_banks"
    )
    atoms, _pairs = _spread_pairs(2049)
    table = "".join(atoms[row % len(atoms)] for row in range(4096))
    monkeypatch.setattr(
        module, "sparse_mask_model", lambda *_a, **_k: pytest.fail("clock rejected")
    )
    assert sparse_class_bank_candidate(table) is None


@pytest.mark.slow
def test_public_sparse_masks_admit_513_classes_beyond_all_three_fold_orders() -> None:
    atoms, pairs = _spread_pairs(513)
    table = "".join(atoms[(row * 509) % 513] for row in range(1024))
    orders = [table] + [
        "".join(table[i :: 1 << k] for i in range(1 << k)) for k in (3, 4)
    ]
    assert [len(_dag(word, 17)[0]) for word in orders] == [2065, 2532, 2482]
    assert all(len(_dag(word, 17)[0]) ** 2 > 4 * len(table) for word in orders)
    code = circuit_diagram(table)
    lines = code.splitlines()
    assert len(lines) * max(map(len, lines)) == 31_716_375
    assert len(code) == 30_228_859
    rows = sorted(
        {
            0,
            len(table) - 1,
            *((p << 7) + pairs[(p * 509) % 513][0] for p in (0, 512, 1023)),
        }
    )
    assert _execute(table, code, rows) == 24
