"""Cooperative results retain finalized output and known VM input usage."""

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.runtime._execution import interpreter_module, run_prepared
from esolangs.runtime._lifecycle import Completion
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import _capture_result, complete_vm, make_vm
from tests.support.reference import REFERENCE


def test_bounded_and_native_input_usage_agree():
    native = run_prepared(
        REFERENCE,
        interpreter_module(REFERENCE)._execute,
        ",.",
        ScriptedIO("é"),
        None,
    )
    bounded = esolangs._run_bounded_result(REFERENCE, ",.", stdin="é", max_steps=2)
    assert bounded[:4] == native[:4] == ("é", 1, 1, 0)
    assert native.completion.kind is Completion.HALTED
    assert bounded.completion.kind is Completion.HALTED
    assert esolangs.run(REFERENCE, ",.", stdin="é", max_steps=2) == bounded.output


def test_post_halt_result_follows_the_final_dump():
    name = next(
        name
        for name, lang in LANGUAGES.items()
        if lang.parameterized
        and lang.contract.answer_mode != "termination"
        and esolangs.describe(name)["dumps_on_the_post_halt_step"]
    )
    source = esolangs.instantiate(name, esolangs.generate(name, "01"), [1])
    result = esolangs._run_bounded_result(name, source, max_steps=1000)
    assert result.completion.kind is Completion.POST_HALT
    assert result.completion.cycle is None
    assert esolangs.read_answer(name, result.output) == "1"
    assert (result.input_position, result.input_reads, result.input_past_end) == (
        0,
        0,
        0,
    )


def test_step_exhaustion_does_not_publish_a_completed_result():
    with pytest.raises(esolangs.ExecutionTimeoutError, match="max_steps") as caught:
        esolangs._run_bounded_result(REFERENCE, "+.[]", max_steps=10)
    assert caught.value.partial_output == "\x01"
    assert caught.value.bound == "max_steps"


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
    assert result.output == "custom"
    assert (result.input_position, result.input_reads, result.input_past_end) == (
        None,
        None,
        None,
    )
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
    assert debugger.result == esolangs.ExecutionResult("", 0, 0, 0, steps=0)
    debugger.step()
    assert debugger.result.steps == 1
    assert debugger.result.completion is None
    debugger.step()
    assert debugger.result.output == "é"
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        debugger.step()
    assert caught.value.execution == debugger.result
    assert debugger.result == esolangs.ExecutionResult("é", 1, 1, 1, steps=2)


def test_debugger_completion_does_not_count_idle_steps():
    from esolangs.debugger import make_debugger

    debugger = make_debugger(REFERENCE, "+.")
    assert debugger.run(max_steps=2) == "halted"
    result = debugger.result
    assert result.steps == 2
    assert result.completion.kind is Completion.HALTED
    debugger.step()
    assert debugger.run(max_steps=0) == "halted"
    assert debugger.result == result


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
    before = debugger.result
    assert before.completion is None
    debugger.step()
    assert debugger.result.steps == before.steps
    assert debugger.result.completion.kind is Completion.POST_HALT
    assert esolangs.read_answer(name, debugger.result.output) == "1"


def test_debugger_does_not_invent_periodic_completion():
    from esolangs.debugger import Debugger

    class Interrupted:
        halted = True
        steppable_to_answer = False
        dumps_on_the_post_halt_step = False
        output = "unproven"

        def step(self):
            pass

    result = Debugger(Interrupted()).result
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
        assert debugger.result.steps < 10000
        debugger.step()
    steps = debugger.result.steps
    original = debugger.vm.step

    def fail():
        raise esolangs.HaltError("dump failed")

    monkeypatch.setattr(debugger.vm, "step", fail)
    with pytest.raises(esolangs.HaltError, match="dump failed") as caught:
        getattr(debugger, drive)()
    assert caught.value.execution == debugger.result
    assert debugger.result.completion is None
    assert debugger.result.steps == steps
    monkeypatch.setattr(debugger.vm, "step", original)
    assert debugger.run(max_steps=0) == "halted"
    assert debugger.result.completion.kind is Completion.POST_HALT
    assert debugger.result.steps == steps
    assert esolangs.read_answer(name, debugger.result.output) == "1"


def test_error_execution_annotation_resolves_public_result_type():
    from typing import get_type_hints

    assert get_type_hints(esolangs.EsolangError)["execution"] == (
        esolangs.ExecutionResult | None
    )
