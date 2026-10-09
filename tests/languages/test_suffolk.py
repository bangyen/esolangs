"""Suffolk through the shared API, CLI and machinery."""

import warnings

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.debugger import complete_vm
from esolangs.vm import (
    make_vm,
    run_until_halt,
    run_until_halt_or_cycle,
    run_until_halt_or_value_growth,
)
from tests.generator_support import evaluate_generated
from tests.test_stepping_parity import _STEP_BUDGET, _row


class TestSelfHaltsIsAWarningNotAGuarantee:
    """``False`` used to promise the step loop never returns.  It can."""

    def test_suffolk_halts_under_a_bare_step_loop(self) -> None:
        """The refutation, run rather than asserted."""
        assert esolangs.describe("Suffolk")["self_halts"] is False
        program = esolangs.generate("Suffolk", "0110")
        vm = debugger_api.make_vm(
            "Suffolk", program, stdin=esolangs.encode_inputs("Suffolk", [1, 0])
        )
        steps = 0
        while not vm.halted and steps < 100_000:
            vm.step()
            steps += 1
        assert vm.halted, "Suffolk did not halt, so the old wording was right"
        assert vm.output == "1"

    def test_the_docstring_no_longer_promises_otherwise(self) -> None:
        """The wording is the fix, so the wording is what is checked."""
        doc = debugger_api.VM.self_halts.__doc__ or ""
        assert "does not promise" in doc
        assert "Suffolk" in doc


def test_isolated_evaluation_requires_a_deadline():
    with pytest.raises(esolangs.ArgumentError, match="finite"):
        evaluate_generated("Suffolk", "0110", None, isolated=True)


@pytest.mark.parametrize("limit", [0, 1])
def test_value_growth_detector_accepts_eof_halt_at_step_limit(limit: int) -> None:
    machine = make_vm("Suffolk", ",")
    if limit == 0:
        machine.step()
    assert run_until_halt_or_value_growth(machine, limit) is True


@pytest.mark.medium
def test_a_non_self_halting_machine_can_already_be_finished():

    vm = make_vm("Suffolk", ",", stdin="1")
    assert not vm.self_halts
    assert run_until_halt(vm, 2)
    assert complete_vm(vm, max_steps=0) == esolangs.run("Suffolk", ",", stdin="1")


def test_the_value_growth_detector_proves_a_climbing_cell() -> None:
    """Suffolk's ``>>!`` loops climb in value on a tape that never grows."""
    climbing = ">>!>>!>>!>>!>>!>>!>>!>>!>>>!>>!>>!>><!>>"
    assert run_until_halt_or_value_growth(make_vm("Suffolk", climbing)) is False
    lapping = make_vm("Suffolk", "1{z:[}] !. ;")
    assert run_until_halt_or_value_growth(lapping) is False


def test_the_value_growth_detector_declines_a_repeating_program() -> None:
    """A program that cycles is the cycle detector's, and is not certified."""
    sample = "!" * 66 + "<."
    assert run_until_halt_or_cycle(make_vm("Suffolk", sample)) is False
    with pytest.raises(TimeoutError):
        run_until_halt_or_value_growth(make_vm("Suffolk", sample), 20_000)

    # `<` alone rewinds to a cell it already read: a repeat, not a climb.
    with pytest.raises(TimeoutError):
        run_until_halt_or_value_growth(make_vm("Suffolk", "<"), 5_000)


def test_a_language_whose_documented_stop_is_eof_is_not_warned_about() -> None:
    """Suffolk's programs end *by* running out of input."""

    program = esolangs.generate("Suffolk", "0110")
    stdin = esolangs.encode_inputs("Suffolk", [1, 0], truth_table="0110")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert esolangs.run("Suffolk", program, stdin=stdin, timeout=20) == "1"
    assert not caught


def test_suffolk_no_longer_disagrees_with_itself() -> None:
    """``run`` answered and the debugger raised, for the same call."""
    table = "0110"
    for bits, want in (([0, 0], "0"), ([0, 1], "1"), ([1, 0], "1"), ([1, 1], "0")):
        program, stdin = _row("Suffolk", table, bits)
        assert esolangs.run("Suffolk", program, stdin=stdin, timeout=20) == want
        debugger = debugger_api.make_debugger("Suffolk", program, stdin=stdin)
        assert debugger.run(max_steps=_STEP_BUDGET) == "halted"
        assert debugger.output == want
