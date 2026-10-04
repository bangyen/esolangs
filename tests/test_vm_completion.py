"""Completion returns run's output, including delayed state dumps."""

import pytest

import esolangs
from esolangs.debugger import complete_vm, make_vm
from tests.samples import NONDETERMINISTIC_AGAINST_RUN, SAMPLES


@pytest.mark.medium
@pytest.mark.parametrize("name", sorted(set(SAMPLES) - NONDETERMINISTIC_AGAINST_RUN))
def test_completion_agrees_with_running(name):
    source, stdin = SAMPLES[name]
    vm = make_vm(name, source, stdin)
    if not vm.self_halts:
        with pytest.raises(esolangs.ArgumentError, match="self-halts"):
            complete_vm(vm)
        return
    expected = esolangs.run(name, source, stdin)
    assert complete_vm(vm) == expected
    state = vm.snapshot()
    assert complete_vm(vm, max_steps=0) == expected
    assert vm.snapshot() == state


@pytest.mark.medium
def test_exhaustion_keeps_partial_state_and_can_resume():
    vm = make_vm("brainfuck", "+.")
    with pytest.raises(esolangs.InterpreterLimitError):
        complete_vm(vm, max_steps=1)
    assert vm.output == ""
    assert complete_vm(vm, max_steps=2) == "\x01"


@pytest.mark.parametrize("budget", [-1, True, 1.5])
def test_completion_rejects_invalid_budgets(budget):
    with pytest.raises(esolangs.ArgumentError):
        complete_vm(make_vm("brainfuck", "+."), max_steps=budget)


@pytest.mark.medium
def test_completion_can_opt_out_of_the_step_budget():
    assert complete_vm(make_vm("brainfuck", "+."), max_steps=None) == "\x01"


@pytest.mark.medium
def test_a_non_self_halting_machine_can_already_be_finished():
    from esolangs.vm import run_until_halt

    vm = make_vm("Suffolk", ",", "1")
    assert not vm.self_halts
    assert run_until_halt(vm, 2)
    assert complete_vm(vm, max_steps=0) == esolangs.run("Suffolk", ",", "1")
