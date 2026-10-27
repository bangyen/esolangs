"""Executed block-pool routing, pulse, workspace, and size controls."""

from unittest import mock

import pytest

from esolangs.languages.circuit_diagram.generator import (
    _linear_shared_layout,
    circuit_diagram,
)
from esolangs.languages.circuit_diagram.generator.hlayout import _h_term_layout
from esolangs.languages.circuit_diagram.generator.hpool import (
    _large_pool_layout,
    _pool_layout,
)
from esolangs.languages.circuit_diagram.interpreter import _compile, _Machine
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.support.witness_tables import dense


def _best_linear_fold(table, n):
    """Return the smallest-area complete fixed-order fold."""
    models: list = []
    _linear_shared_layout(table, n, models)
    return min(models, key=lambda m: m.bounds()[0] * m.bounds()[1])


def _execute(table, code, rows=None):
    n = len(table).bit_length() - 1
    lines = code.splitlines()
    maximum = 0
    selected = range(1 << n) if rows is None else rows
    # A program past the compile cache's text bound reparses per machine:
    # 8 s a row at 21M cells, 290 s of the 129-class check's 36 rows.
    topology = _compile(tuple(lines))
    for row in selected:
        io = ScriptedIO(f"{row:0{n}b}")
        with mock.patch(f"{_Machine.__module__}._compile", return_value=topology):
            vm = _Machine(lines, io)
        assert io.progress() == n
        written = WrittenState(vm.snapshot()) if row in (0, (1 << n) - 1) else None
        commands = 0
        while not vm.halted and commands <= 2 * n + 2:
            vm.step()
            commands += 1
            if written is not None:
                written.sample(vm.snapshot())
        assert vm.halted
        assert io.getvalue() == table[row], (row, io.getvalue())
        assert commands <= 2 * n + 2
        if written is not None:
            assert written.bits <= 7 * (1 << n) + 2 * n - 9
        maximum = max(maximum, commands)
    return maximum


@pytest.mark.medium
@pytest.mark.parametrize("n", [8, 9])
def test_public_dense_candidates_beat_minterms_without_relaxing_contracts(n) -> None:
    table = dense(n)
    model = _large_pool_layout(table)
    code = circuit_diagram(table)
    height, width = model.bounds()
    lines = code.splitlines()
    assert len(lines) * max(map(len, lines)) <= height * width
    assert len(code) == {8: 136_120, 9: 258_216}[n]
    legacy = _h_term_layout(table)
    assert model.bounds()[0] * model.bounds()[1] < (
        legacy.bounds()[0] * legacy.bounds()[1]
    )
    _execute(table, code)


@pytest.mark.medium
@pytest.mark.parametrize("ignored", [0, 4, 8])
def test_projected_pool_reads_every_original_port_in_order(ignored) -> None:
    kept = [index for index in range(9) if index != ignored]
    core = dense(8)
    table = "".join(
        core[sum(((row >> (8 - at)) & 1) << (7 - i) for i, at in enumerate(kept))]
        for row in range(512)
    )
    model = _large_pool_layout(core, input_order=kept, port_inputs=9)
    code = circuit_diagram(table)
    height, width = model.bounds()
    lines = code.splitlines()
    assert len(lines) * max(map(len, lines)) <= height * width
    _execute(table, code)


@pytest.mark.parametrize(
    ("order", "ports"), [(list(range(8)), 9), ([0] * 9, 9), (list(range(9)), 8)]
)
def test_invalid_input_ports_abort(order, ports) -> None:
    with pytest.raises(ValueError, match="distinct original ports"):
        _large_pool_layout(dense(9), input_order=order, port_inputs=ports)


def test_unsupported_tables_abort() -> None:
    with pytest.raises(ValueError, match="two prefix inputs"):
        _pool_layout(dense(8), 7, input_order=None, port_inputs=None)
    with pytest.raises(ValueError, match="selected row"):
        _large_pool_layout("0" * 512)
