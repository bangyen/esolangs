"""Executed block-pool routing, pulse, workspace, and size controls."""

from functools import cache
from math import prod
from unittest import mock

import pytest

import esolangs.languages.circuit_diagram.interpreter._functions as functions
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
from scripts.docs.evidence import construction_boundaries
from tests.support.screen_support import ignore
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
    # Reparse avoidance: 21M-cell code took 8s/row, 290s for 36 rows.
    topology = _compile(tuple(lines))
    expand = functions._expand_function_body
    expanded = cache(lambda gate, body, bindings: expand(gate, body, dict(bindings)))
    # Width substitution reuse cut n=7/8/9 from .24/.91/3.49s to .20/.75/2.67s.
    # Every function still executes; traces, output and input cursors matched.
    with mock.patch.object(
        functions,
        "_expand_function_body",
        new=lambda gate, body, bindings: expanded(gate, body, tuple(bindings.items())),
    ):
        for row in range(1 << n) if rows is None else rows:
            io = ScriptedIO(f"{row:0{n}b}")
            with mock.patch(f"{_Machine.__module__}._compile", return_value=topology):
                vm = _Machine(lines, io)
            assert io.progress() == n
            written = (
                WrittenState(vm.workspace_snapshot())
                if row in (0, (1 << n) - 1)
                else None
            )
            commands = 0
            while not vm.halted and commands <= 2 * n + 2:
                vm.step()
                commands += 1
                if written is not None:
                    written.sample(vm.workspace_snapshot())
            assert vm.halted
            assert io.getvalue() == table[row], (row, io.getvalue())
            assert commands <= 2 * n + 2
            if written is not None:
                assert written.bits <= 7 * (1 << n) + 2 * n - 9
            maximum = max(maximum, commands)
    return maximum


@pytest.mark.medium
@pytest.mark.parametrize(
    "witness",
    construction_boundaries("Circuit Diagram")["single_atom_to_prefix_pool"],
    ids=lambda witness: f"n{witness.arity}",
)
def test_public_dense_candidates_beat_minterms_without_relaxing_contracts(
    witness, monkeypatch
) -> None:
    from esolangs.languages.circuit_diagram.generator import hpool

    table = witness.table()
    routed = []
    finish = hpool._finish_pool

    def observe(build):
        routed.append(build)
        return finish(build)

    with monkeypatch.context() as scope:
        scope.setattr(hpool, "_finish_pool", observe)
        model = _large_pool_layout(table)
    assert len(routed) == int(witness.arity == 9)
    if routed:
        _execute(table, model.render(), (0, 1, 128, 255, 256, 511))
    code = circuit_diagram(table)
    lines = code.splitlines()
    assert len(lines) * max(map(len, lines)) <= prod(model.bounds())
    assert prod(model.bounds()) < prod(_h_term_layout(table).bounds())
    _execute(table, code)


@pytest.mark.medium
@pytest.mark.parametrize("ignored", [0, 4, 8])
def test_projected_pool_reads_every_original_port_in_order(ignored) -> None:
    kept = [index for index in range(9) if index != ignored]
    core = dense(8)
    table = ignore(core, ignored)
    model = _large_pool_layout(core, input_order=kept, port_inputs=9)
    code = circuit_diagram(table)
    lines = code.splitlines()
    assert len(lines) * max(map(len, lines)) <= prod(model.bounds())
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
