"""Sparse occurrence-position masks folded from one shared work budget."""

from __future__ import annotations

import pytest

from esolangs.languages.circuit_diagram.generator import _dag
from esolangs.languages.circuit_diagram.generator.sparse_masks import (
    _sparse_mask_dag,
    _SparseWork,
    sparse_mask_model,
)
from esolangs.languages.circuit_diagram.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from tests.support.witness_tables import dense, parity


def _positions(table: str) -> list[int]:
    """The sorted rows a dense mask table sets."""
    return [row for row, bit in enumerate(table) if bit == "1"]


def _feed(mask: str, prefix: int, order: list[int], ports: int) -> None:
    """Run ``mask``'s model over every row and compare each printed bit."""
    model = sparse_mask_model(
        _positions(mask),
        prefix,
        input_order=order,
        port_inputs=ports,
        work=_SparseWork(1 << 20),
    )
    assert model is not None
    lines = model.render().splitlines()
    for row, expected in enumerate(mask):
        bits = [(row >> (prefix - 1 - i)) & 1 for i in range(prefix)]
        stdin = [0] * ports
        for index, bit in enumerate(bits):
            stdin[order[index]] = bit
        io = ScriptedIO("".join(map(str, stdin)))
        vm = _Machine(lines, io)
        assert io.progress() == ports
        for _ in range(2 * ports + 2):
            if vm.halted:
                break
            vm.step()
        assert vm.halted
        assert io.getvalue() == expected, (row, expected)


@pytest.mark.parametrize("n", [1, 2, 3])
def test_sparse_dag_matches_the_dense_fold_for_every_table(n: int) -> None:
    """All ``2**(2**n)`` tables through three inputs, constants included."""
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        work = _SparseWork(1 << 20)
        assert _sparse_mask_dag(_positions(table), n, work) == _dag(table, n), table
        assert work.used > 0


@pytest.mark.parametrize("n", [8, 10, 13])
def test_sparse_dag_matches_dense_fold_across_large_range_boundaries(n: int) -> None:
    masks = [dense(n), parity(n), "1" + "0" * ((1 << n) - 2) + "1"]
    for table in masks:
        assert _sparse_mask_dag(_positions(table), n, _SparseWork(1 << 20)) == _dag(
            table, n
        )


@pytest.mark.parametrize(
    ("rows", "prefix", "message"),
    [
        ([0], 0, "at least one prefix input"),
        ([2], 1, "mask positions must be sorted"),
        ([1, 1], 2, "mask positions must be sorted"),
        ([1, 0], 2, "mask positions must be sorted"),
        ([-1], 2, "mask positions must be sorted"),
    ],
)
def test_invalid_sparse_masks_abort(rows: list[int], prefix: int, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _sparse_mask_dag(rows, prefix, _SparseWork(1 << 20))


def test_sparse_mask_dag_aborts_over_budget_with_a_positive_control() -> None:
    table = dense(6)
    rows = _positions(table)
    tight = _SparseWork(1)
    assert _sparse_mask_dag(rows, 6, tight) is None
    assert tight.used > tight.limit
    # The same probe under a budget that covers it still reproduces _dag,
    # so the abort above was the budget, not the input.
    control = _SparseWork(1 << 20)
    assert _sparse_mask_dag(rows, 6, control) == _dag(table, 6)
    assert control.used <= control.limit

    spent = control.used
    assert _sparse_mask_dag(rows, 6, _SparseWork(spent)) is not None
    short = _SparseWork(spent - 1)
    assert _sparse_mask_dag(rows, 6, short) is None
    assert short.used > short.limit
    # Every tighter budget aborts wherever it runs out, never with a partial DAG.
    for limit in range(spent):
        assert _sparse_mask_dag(rows, 6, _SparseWork(limit)) is None


def test_sparse_mask_model_returns_none_over_budget() -> None:
    rows = _positions(dense(6))
    assert sparse_mask_model(rows, 6, work=_SparseWork(1)) is None
    assert sparse_mask_model(rows, 6, work=_SparseWork(1 << 20)) is not None


def test_mask_validation_and_layout_are_charged_before_work(monkeypatch) -> None:
    import importlib

    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.sparse_masks"
    )
    rows = [0, 3]
    fold_work = _SparseWork(1 << 20)
    assert _sparse_mask_dag(rows, 3, fold_work) is not None

    def unexpected(*_args):
        pytest.fail("an exhausted budget must reject before allocation")

    monkeypatch.setattr(module, "_validated_rows", unexpected)
    assert _sparse_mask_dag(rows, 3, _SparseWork(0)) is None
    monkeypatch.undo()
    monkeypatch.setattr(module, "_Builder", unexpected)
    assert sparse_mask_model(rows, 3, work=_SparseWork(fold_work.used)) is None


@pytest.mark.medium
def test_sparse_mask_model_keeps_ignored_input_ports() -> None:
    """Two inputs never reach the fold, but all four ports are still read."""
    prefix = 4
    mask = "".join(str(((row >> 3) & 1) ^ (row & 1)) for row in range(1 << prefix))
    _feed(mask, prefix, list(range(prefix)), prefix)


@pytest.mark.medium
def test_sparse_mask_model_honors_read_order_and_extra_ports() -> None:
    prefix, ports = 4, 6
    _feed(parity(prefix), prefix, [3, 1, 0, 2], ports)


@pytest.mark.medium
@pytest.mark.parametrize("bit", ["0", "1"])
def test_sparse_mask_model_folds_constants_over_the_first_port(bit: str) -> None:
    _feed(bit * 8, 3, [0, 1, 2], 3)
