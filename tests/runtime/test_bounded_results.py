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
        interpreter_module(REFERENCE).run,
        ",.",
        ScriptedIO("é"),
        None,
        report_required=False,
    )
    bounded = esolangs._run_bounded_result(REFERENCE, ",.", stdin="é", max_steps=2)
    assert bounded[:4] == native[:4] == ("é", 1, 1, 0)
    assert native.completion is None
    assert bounded.completion.kind is Completion.HALTED
    assert esolangs.run(REFERENCE, ",.", stdin="é", max_steps=2) == bounded.output


def test_post_halt_result_follows_the_final_dump():
    name = next(
        name
        for name, lang in LANGUAGES.items()
        if lang.runtime.completion_entrypoint is not None
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
