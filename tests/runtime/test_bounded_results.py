"""Cooperative results retain finalized output and known VM input usage."""

import pytest

import esolangs
import esolangs.operations.execution as _execution_operations
from esolangs.registry import LANGUAGES
from esolangs.runtime._lifecycle import Completion
from esolangs.vm import _capture_result, complete_vm, make_vm
from tests.support.reference import REFERENCE


def test_step_exhaustion_does_not_publish_a_completed_result(monkeypatch):
    from esolangs.debugger import Debugger

    def refuse_debugger(*_args, **_kwargs):
        raise AssertionError("bounded execution must not construct a debugger")

    monkeypatch.setattr(Debugger, "__init__", refuse_debugger)
    with pytest.raises(esolangs.ExecutionTimeoutError, match="max_steps") as caught:
        _execution_operations._execute_bounded(REFERENCE, "+.[]", max_steps=10).unwrap()
    assert caught.value.partial_output == "\x01"
    assert caught.value.bound == "max_steps"
    result = _execution_operations._execute_bounded(
        REFERENCE, "+.", max_steps=2
    ).unwrap()
    assert result.output == "\x01"
    assert result.steps == 2


def test_an_active_vm_has_no_successful_result():
    with pytest.raises(esolangs.ArgumentError, match="requires a halted VM"):
        _capture_result(make_vm(REFERENCE, "+."))


def test_custom_vm_io_fields_stay_caller_owned():
    class Custom:
        halted = True
        dumps_on_the_post_halt_step = False
        output = "custom"
        _io = object()

    result = _capture_result(Custom())
    assert result[:4] == ("custom", None, None, None)
    assert result.completion.kind is Completion.HALTED


def test_vm_capture_does_not_call_an_unrelated_instance_attribute():
    vm = make_vm(REFERENCE, "+.")
    complete_vm(vm)
    vm._result = "caller metadata"
    result = _capture_result(vm)
    assert result.output == "\x01"
    assert result.input_reads == 0


def test_debugger_observations_follow_steps_and_failures():
    from esolangs.debugger import make_debugger

    debugger = make_debugger(REFERENCE, ",.,", stdin="é")
    assert debugger.observation == esolangs.ExecutionResult("", 0, 0, 0, steps=0)
    debugger.step()
    assert debugger.observation.steps == 1
    assert debugger.observation.completion is None
    debugger.step()
    assert debugger.observation.output == "é"
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        debugger.step()
    assert caught.value.observation == debugger.observation
    assert debugger.observation == esolangs.ExecutionResult("é", 1, 1, 1, steps=2)


def test_debugger_completion_does_not_count_idle_steps():
    from esolangs.debugger import make_debugger

    debugger = make_debugger(REFERENCE, "+.")
    assert debugger.run(max_steps=2) == "halted"
    result = debugger.observation
    assert result.steps == 2
    assert result.completion.kind is Completion.HALTED
    debugger.step()
    assert debugger.run(max_steps=0) == "halted"
    assert debugger.observation == result


def test_post_halt_completion_stays_pending_until_dump():
    from esolangs.debugger import make_debugger

    name = next(
        name
        for name, lang in LANGUAGES.items()
        if lang.parameterized
        and lang.contract.answer_mode != "termination"
        and esolangs.describe(name)["dumps_on_the_post_halt_step"]
    )
    source = esolangs.instantiate(name, esolangs.generate(name, "01"), [1])
    debugger = make_debugger(name, source)
    # Stop at halt before the completion step.
    while not debugger.halted:
        debugger.step()
    before = debugger.observation
    assert before.completion is None
    debugger.step()
    assert debugger.observation.steps == before.steps
    assert debugger.observation.completion.kind is Completion.POST_HALT
    assert esolangs.read_answer(name, debugger.observation.output) == "1"


def test_debugger_does_not_invent_periodic_completion():
    from esolangs.debugger import Debugger

    class Interrupted:
        halted = True
        steppable_to_answer = False
        dumps_on_the_post_halt_step = False
        output = "unproven"

        def step(self):
            pass

    result = Debugger(Interrupted()).observation
    assert result.output == "unproven"
    assert result.completion is None
    assert result.input_position is None


@pytest.mark.parametrize("drive", ["step", "run"])
def test_failed_dump_remains_unfinished_and_can_be_retried(monkeypatch, drive):
    from esolangs.debugger import make_debugger
    from tests.support.pick import one_where

    name = one_where(
        lambda info: info["answer_mode"] != "termination",
        boolean_generator=True,
        parameterized=True,
        dumps_on_the_post_halt_step=True,
        steppable_to_answer=True,
    )[0]
    source = esolangs.instantiate(name, esolangs.generate(name, "01"), [1])
    debugger = make_debugger(name, source)
    assert debugger.run(max_steps=0) == "max_steps"
    while not debugger.halted:
        assert debugger.observation.steps < 10000
        debugger.step()
    steps = debugger.observation.steps
    original = debugger.vm.step

    def fail():
        raise esolangs.HaltError("dump failed")

    monkeypatch.setattr(debugger.vm, "step", fail)
    with pytest.raises(esolangs.HaltError, match="dump failed") as caught:
        getattr(debugger, drive)()
    assert caught.value.observation == debugger.observation
    assert debugger.observation.completion is None
    assert debugger.observation.steps == steps
    monkeypatch.setattr(debugger.vm, "step", original)
    assert debugger.run(max_steps=0) == "halted"
    assert debugger.observation.completion.kind is Completion.POST_HALT
    assert debugger.observation.steps == steps
    assert esolangs.read_answer(name, debugger.observation.output) == "1"


def test_error_observation_annotation_resolves_public_result_type():
    from typing import get_type_hints

    assert get_type_hints(esolangs.EsolangError)["observation"] == (
        esolangs.ExecutionResult | None
    )
