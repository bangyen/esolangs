"""Forbin through the shared API, CLI and machinery."""

import pytest

import esolangs.debugger as debugger_api
from esolangs.exceptions import InputExhaustedError
from esolangs.vm import run_until_halt_or_ancestor
from tests.support.vm_support import assert_proof_fault


@pytest.mark.parametrize("debugged", [False, True])
def test_live_detectors_keep_vm_fault_evidence(*, debugged: bool) -> None:
    assert_proof_fault(
        run_until_halt_or_ancestor,
        "Forbin",
        "main { out 0,1,0,0,0,0,0,1; x = (in 0); }",
        InputExhaustedError,
        "A",
        debugged=debugged,
    )


class TestForbin:
    def test_locals_and_cursor(self) -> None:
        vm = debugger_api.make_vm("Forbin", "main { x = 1; }")
        assert vm.ip == (0,)
        assert vm.memory == []
        assert vm.stack == []
        vm.step()
        assert vm.ip == (1,)
        assert vm.memory == [1]
        vm.step()  # main's body is exhausted; the frame pops
        assert vm.halted
        assert vm.memory == []  # the frame stack has emptied

    def test_ip_exposes_the_call_stack(self) -> None:
        # a statement-position call pushes a new frame, deepening ip
        vm = debugger_api.make_vm("Forbin", "main { f 0; }\nf x { y = 1; }")
        assert vm.ip == (0,)
        vm.step()  # f 0; pushes a frame for f, advancing main's own cursor
        assert vm.ip == (1, 0)
        vm.step()  # y = 1; inside f
        assert vm.ip == (1, 1)
        vm.step()  # f's body is exhausted; the frame pops
        assert vm.ip == (1,)
        vm.step()  # main's body is exhausted; the frame pops
        assert vm.halted
