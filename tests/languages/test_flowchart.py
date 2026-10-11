"""Flowchart through the shared API, CLI and machinery."""

import warnings

import esolangs
import esolangs.debugger as debugger_api
from tests.support.samples import FLOWCHART_CAT, FLOWCHART_TRUTH_MACHINE
from tests.vm.test_vm import _run_all
from tests.vm.test_vm_protocol import assert_starts_downward


class TestTheDebuggerWarnsAboutStdinToo:
    """``run`` warned and the debugger did not, which is backwards."""

    def test_the_debugger_says_what_run_says(self) -> None:
        """Flowchart under-fed: one line to a two-input program."""
        program = esolangs.generate("Flowchart", "0110")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            esolangs.run("Flowchart", program, stdin="1\n", timeout=10)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            debugger_api.make_debugger("Flowchart", program, stdin="1\n").run(
                timeout=10
            )

    def test_a_correct_input_stays_silent(self) -> None:
        """A warning that fires on correct input is worth less than none."""
        program = esolangs.generate("Flowchart", "0110")
        stdin = esolangs.encode_inputs("Flowchart", [1, 0], truth_table="0110")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            debugger_api.make_debugger("Flowchart", program, stdin=stdin).run(
                timeout=10
            )

    def test_it_is_said_once(self) -> None:
        """``run`` on a halted machine returns at once; re-warning is noise."""
        program = esolangs.generate("Flowchart", "0110")
        debugger = debugger_api.make_debugger("Flowchart", program, stdin="1\n")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            debugger.run(timeout=10)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            debugger.run(timeout=10)


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
