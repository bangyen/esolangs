"""Flowchart through the shared API, CLI and machinery."""

import esolangs
import esolangs.debugger as debugger_api
from esolangs import run
from tests.support.samples import FLOWCHART_CAT, FLOWCHART_TRUTH_MACHINE
from tests.support.vm_support import _run_all, assert_starts_downward


class TestDebuggerInputAndHalting:
    def test_underfed_input_matches_run(self) -> None:
        program = esolangs.generate("Flowchart", "0110")
        output = run(
            "Flowchart",
            program,
            stdin="1\n",
            limits=esolangs.ExecutionLimits(execution_timeout=10),
        ).output
        debugger = debugger_api.make_debugger("Flowchart", program, stdin="1\n")
        assert (
            debugger.run(limits=esolangs.ExecutionLimits(execution_timeout=10))
            == "halted"
        )
        assert debugger.vm.output == output

    def test_encoded_input_computes_the_answer(self) -> None:
        program = esolangs.generate("Flowchart", "0110")
        stdin = esolangs.encode_inputs("Flowchart", [1, 0], truth_table="0110")
        debugger = debugger_api.make_debugger("Flowchart", program, stdin=stdin)
        assert (
            debugger.run(limits=esolangs.ExecutionLimits(execution_timeout=10))
            == "halted"
        )
        assert esolangs.read_answer("Flowchart", debugger.vm.output) == "1"

    def test_repeated_run_preserves_halted_state(self) -> None:
        program = esolangs.generate("Flowchart", "0110")
        debugger = debugger_api.make_debugger("Flowchart", program, stdin="1\n")
        assert (
            debugger.run(limits=esolangs.ExecutionLimits(execution_timeout=10))
            == "halted"
        )
        before = debugger.vm.snapshot(), debugger.vm.output
        assert (
            debugger.run(limits=esolangs.ExecutionLimits(execution_timeout=10))
            == "halted"
        )
        assert (debugger.vm.snapshot(), debugger.vm.output) == before


class TestFlowchart:
    def test_live_pointer_position_and_heading(self) -> None:
        vm = debugger_api.make_vm("Flowchart", FLOWCHART_TRUTH_MACHINE, stdin="0\n")
        assert vm.ip == (0, 10, 0, 1)  # on the opening ( ), heading east
        assert vm.stack == []
        vm.step()
        assert vm.ip == (2, 12, 1, 0)  # rode the path, read at / /, heading south

    def test_ip_is_none_once_every_pointer_has_stopped(self) -> None:
        """``ip`` reports the first live pointer, so a finished run has none."""
        vm = debugger_api.make_vm("Flowchart", FLOWCHART_TRUTH_MACHINE, stdin="0\n")
        assert _run_all(vm) == "\x00"  # one zero bit, padded at halt
        assert vm.ip is None

    def test_the_deque_holds_what_the_pointers_read(self) -> None:
        """The cat reads its bits onto the shared tape before printing them."""
        vm = debugger_api.make_vm("Flowchart", FLOWCHART_CAT, stdin="1\n")
        while not vm.halted and not vm.memory:
            vm.step()
        assert vm.memory == [1]


def test_the_first_move_is_down_the_rows() -> None:
    """It begins vertically, so ``VM.ip``'s first component moves first."""
    assert_starts_downward("Flowchart", 1)
