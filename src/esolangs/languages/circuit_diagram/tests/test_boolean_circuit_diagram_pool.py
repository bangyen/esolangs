"""Executed block-pool routing, pulse, workspace, and size controls."""

import importlib
import random

import pytest

from esolangs.languages.circuit_diagram.generator import circuit_diagram
from esolangs.languages.circuit_diagram.generator.hlayout import _h_term_layout
from esolangs.languages.circuit_diagram.generator.hpool import (
    _h_pool_layout,
    _h_pool_size,
)
from esolangs.languages.circuit_diagram.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.support.witness_tables import dense, nested_dense, parity


@pytest.mark.medium
def test_public_pool_admission_preserves_the_minterm_area_ceiling(monkeypatch) -> None:
    generator = importlib.import_module("esolangs.languages.circuit_diagram.generator")
    monkeypatch.setattr(generator, "_linear_shared_layout", lambda *_args: None)
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.hpool"
    )
    monkeypatch.setattr(module, "_large_pool_layout", lambda *_args, **_kwargs: None)
    table = dense(8)
    lattice = _h_term_layout(table)
    height, width = lattice.bounds()

    class Oversized:
        def bounds(self):
            return height + 1, width

        def render(self):
            pytest.fail("oversized pool must not be emitted")

    monkeypatch.setattr(module, "_h_pool_layout", lambda *_args, **_kwargs: Oversized())
    code = circuit_diagram(table)
    assert code == lattice.render()
    _execute(table, code, (0, 255))


@pytest.mark.medium
def test_projected_lattice_remains_available_below_pool_arity(monkeypatch) -> None:
    module = importlib.import_module("esolangs.languages.circuit_diagram.generator")
    monkeypatch.setattr(module, "_linear_shared_layout", lambda *_args: None)
    pools = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.hpool"
    )
    monkeypatch.setattr(pools, "_large_pool_layout", lambda *_args, **_kwargs: None)
    table = "".join(str((row >> 7) & (row & 1)) for row in range(256))
    code = circuit_diagram(table)
    assert code == _h_term_layout("0001", input_order=[0, 7], port_inputs=8).render()
    _execute(table, code)


def _execute(table, code, rows=None):
    n = len(table).bit_length() - 1
    lines = code.splitlines()
    maximum = 0
    selected = range(1 << n) if rows is None else rows
    for row in selected:
        io = ScriptedIO(f"{row:0{n}b}")
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
def test_every_three_input_cofactor_through_a_pool_and_prefix_tree() -> None:
    for start in range(0, 256, 16):
        table = "".join(f"{value:08b}" for value in range(start, start + 16))
        _execute(table, _h_pool_layout(table).render())


@pytest.mark.medium
@pytest.mark.parametrize("n", [8, 9])
def test_public_dense_candidates_beat_minterms_without_relaxing_contracts(n) -> None:
    table = dense(n)
    model = _h_pool_layout(table)
    code = circuit_diagram(table)
    height, width = model.bounds()
    lines = code.splitlines()
    assert len(lines) * max(map(len, lines)) <= height * width
    assert len(code) == {8: 128_824, 9: 258_216}[n]
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
    model = _h_pool_layout(core, input_order=kept, port_inputs=9)
    code = circuit_diagram(table)
    height, width = model.bounds()
    lines = code.splitlines()
    assert len(lines) * max(map(len, lines)) <= height * width
    _execute(table, code)


@pytest.mark.medium
def test_four_input_pool_routes_dense_and_test_free_residuals() -> None:
    rng = random.Random(1)
    table = "".join(rng.choice("01") for _ in range(256))
    _execute(table, _h_pool_layout(table).render())


@pytest.mark.medium
def test_empty_full_and_mixed_pools_fold_before_the_result_tree() -> None:
    table = "0" * 16 + "1" * 16 + parity(4) + dense(4)
    _execute(table, _h_pool_layout(table).render())


@pytest.mark.slow
@pytest.mark.parametrize("arities", [(8, 10, 12), (7, 9, 11)])
def test_pool_text_growth_with_native_positive_controls(arities) -> None:
    sizes = []
    for n in arities:
        table = nested_dense(n)
        code = _h_pool_layout(table).render()
        _execute(table, code, (0, (1 << n) - 1))
        sizes.append(len(code))
    assert (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) <= 4.4


def test_pool_side_closed_form() -> None:
    for tail, leaf in ((3, 96), (4, 192)):
        for m in range(32):
            side = _h_pool_size(2 * m, tail)
            coefficient = leaf + 16 * tail + 72
            assert side == coefficient * 2**m - 32 * m - 16 * tail - 72
            assert side * side < coefficient**2 * 2 ** (2 * m)


@pytest.mark.parametrize(("prefix", "tail"), [(-2, 4), (3, 4), (2, 2)])
def test_unsupported_pool_dimensions_abort(prefix, tail) -> None:
    with pytest.raises(ValueError, match="even prefix"):
        _h_pool_size(prefix, tail)


@pytest.mark.parametrize(
    ("order", "ports"), [(list(range(5)), 6), ([0] * 6, 6), (list(range(6)), 5)]
)
def test_invalid_input_ports_abort(order, ports) -> None:
    with pytest.raises(ValueError, match="distinct original ports"):
        _h_pool_layout(dense(6), input_order=order, port_inputs=ports)


def test_unsupported_tables_abort() -> None:
    with pytest.raises(ValueError, match="two prefix inputs"):
        _h_pool_layout(dense(4))
    with pytest.raises(ValueError, match="selected row"):
        _h_pool_layout("0" * 64)
