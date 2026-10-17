"""Global fold admission and the linear-area local cofactor alternative."""

from __future__ import annotations

import hashlib

import pytest

from esolangs.languages.circuit_diagram.generator import (
    _circuit_diagram_model,
    _dag,
    _linear_shared_layout,
    circuit_diagram,
)
from esolangs.languages.circuit_diagram.generator.hlayout import (
    _h_minterm_sites,
    _h_term_layout,
)
from esolangs.languages.circuit_diagram.generator.hpool import _large_pool_layout
from esolangs.languages.circuit_diagram.interpreter import _Machine
from esolangs.languages.circuit_diagram.tests.test_boolean_circuit_diagram_pool import (
    _execute,
)
from esolangs.runtime.io import ScriptedIO
from tests.support.witness_tables import nested_dense


def _dense(n: int) -> str:
    """The linearity test's sha256 stream table for ``n`` inputs."""
    digest = hashlib.sha256(f"dense:{n}".encode()).digest()
    bits: list[str] = []
    block = 0
    while len(bits) < 2**n:
        digest = hashlib.sha256(digest + bytes([block & 255])).digest()
        bits.extend(str(byte & 1) for byte in digest)
        block += 1
    return "".join(bits[: 2**n])


def _area(model) -> int:
    height, width = model.bounds()
    return height * width


class TestCircuitDiagramShareScope:
    """Complete interval folds beyond the former quadratic node cutoff."""

    @pytest.mark.medium
    def test_complete_shared_fold_passes_the_former_node_cutoff(self) -> None:
        table = _dense(8)
        nodes = len(_dag(table, 8)[0])
        assert nodes**2 > 4 * len(table)  # over the admission cutoff
        assert _area(_circuit_diagram_model(table, None)) < _area(_h_term_layout(table))
        models: list = []
        _linear_shared_layout(table, 8, models)
        assert models
        _execute(table, min(models, key=_area).render())

    @pytest.mark.medium
    def test_the_public_build_admits_smaller_cofactor_candidates(self) -> None:
        table = _dense(8)
        code = circuit_diagram(table)
        lines = code.splitlines()
        assert len(lines) * max(map(len, lines)) <= _area(_large_pool_layout(table))
        assert _area(_large_pool_layout(table)) < _area(_h_term_layout(table))
        _execute(table, code)

    def test_shared_fold_growth_exceeds_the_linear_contract(self) -> None:
        """Same-parity size difference n=8->10 against the x4.4 contract."""
        shared = _area(_circuit_diagram_model(_dense(10), None)) / _area(
            _circuit_diagram_model(_dense(8), None)
        )
        hlay = _area(_h_term_layout(_dense(10))) / _area(_h_term_layout(_dense(8)))
        assert round(shared, 3) == 4.926
        assert hlay <= 4.4 < shared

    @pytest.mark.slow
    def test_exact_area_admission_alone_breaks_measured_text_growth(self) -> None:
        sizes = []
        for n in (8, 10, 12):
            table = nested_dense(n)
            model = _circuit_diagram_model(table, None)
            sites = _h_minterm_sites(n)
            xs, ys = zip(
                *(point for prefix, point in sites.items() if prefix.bit_length() >= 3),
                strict=True,
            )
            floor = (max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1)
            assert _area(model) < floor
            code = model.render()
            sizes.append(len(code))
            for row in (0, (1 << n) - 1):
                io = ScriptedIO(f"{row:0{n}b}")
                vm = _Machine(code.splitlines(), io)
                assert io.progress() == n
                commands = 0
                while not vm.halted and commands <= 2 * n + 2:
                    vm.step()
                    commands += 1
                assert vm.halted
                assert io.getvalue() == table[row]
        ratio = (sizes[2] - sizes[1]) / (sizes[1] - sizes[0])
        assert round(ratio, 3) == 9.455
        assert ratio > 4.4
