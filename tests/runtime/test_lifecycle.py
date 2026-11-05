"""Completion preserves halt boundaries and requires periodic evidence."""

import pytest

from esolangs.exceptions import ExecutionTimeoutError
from esolangs.registry import LANGUAGES
from esolangs.runtime._drive import drive, drive_periodic, finalize
from esolangs.runtime._execution import interpreter_module
from esolangs.runtime._lifecycle import BoundaryCycle, Completion, completion


class _Periodic:
    completion = Completion.PERIODIC
    halted = False

    def __init__(self):
        self.state = 10
        self.steps = 0
        self.interrupted = False
        self.output = ""

    def snapshot(self):
        return self.state

    def interrupt(self):
        self.interrupted = True

    def step(self):
        if self.interrupted:
            self.output = str(self.state)
        else:
            self.state = {10: 11, 11: 0}.get(self.state, (self.state + 1) % 3)
            self.steps += 1


def test_periodic_completion_excludes_the_transient_and_keeps_pass_boundaries():
    machine = _Periodic()
    cycle = drive_periodic(machine, 2)
    assert cycle.first_pass >= 1
    assert cycle.repeat_pass - cycle.first_pass == 3
    assert machine.steps == cycle.repeat_pass * cycle.commands_per_pass
    assert machine.state == cycle.state
    assert machine.output == str(cycle.state)
    assert machine.interrupted
    assert not machine.halted


def test_an_empty_pass_still_renders_the_initial_state():
    machine = _Periodic()
    cycle = drive_periodic(machine, 0)
    assert cycle == BoundaryCycle(10, 0, 1, 0)
    assert machine.steps == 0
    assert machine.output == "10"


def test_periodic_completion_refuses_missing_or_stale_evidence():
    machine = _Periodic()
    with pytest.raises(ValueError, match="needs boundary-cycle evidence"):
        finalize(machine)
    with pytest.raises(ValueError, match="no longer matches"):
        finalize(machine, cycle=BoundaryCycle(0, 0, 1, 2))
    assert not machine.interrupted
    assert machine.steps == 0
    assert machine.output == ""


@pytest.mark.parametrize("policy", [Completion.HALTED, Completion.POST_HALT])
def test_halt_completion_never_executes_an_active_machine(policy):
    machine = _Periodic()
    machine.completion = policy
    with pytest.raises(ValueError, match="requires a halted machine"):
        finalize(machine)
    with pytest.raises(ValueError, match="requires periodic completion"):
        finalize(machine, cycle=BoundaryCycle(10, 0, 1, 2))
    assert machine.steps == 0
    with pytest.raises(ValueError, match="requires periodic completion"):
        drive_periodic(machine, 2)


def test_declared_post_halt_output_remains_available():
    class PostHalt:
        completion = Completion.POST_HALT

        def __init__(self):
            self.halted = False
            self.output = ""

        def step(self):
            if self.halted:
                self.output = "done"
            else:
                self.halted = True

    machine = PostHalt()
    drive(machine)
    assert machine.output == "done"
    assert completion(machine) is Completion.POST_HALT


@pytest.mark.parametrize(
    ("first", "repeat", "stride"), [(-1, 1, 1), (1, 1, 1), (0, 1, -1)]
)
def test_cycle_evidence_needs_ordered_boundaries(first, repeat, stride):
    with pytest.raises(ValueError, match="ordered passes"):
        BoundaryCycle(0, first, repeat, stride)


def test_a_timeout_does_not_finalize_periodic_output():
    class TimedOut(_Periodic):
        def step(self):
            raise ExecutionTimeoutError("test deadline")

    machine = TimedOut()
    with pytest.raises(ExecutionTimeoutError, match="test deadline"):
        drive_periodic(machine, 2)
    assert not machine.interrupted
    assert machine.output == ""


@pytest.mark.parametrize("name", sorted(LANGUAGES))
def test_interpreter_completion_has_one_declaration(name):
    machine = interpreter_module(name)._Machine
    assert isinstance(completion(machine), Completion)
    assert "dumps_on_the_post_halt_step" not in vars(machine)
    assert "steppable_to_answer" not in vars(machine)
