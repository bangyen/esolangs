"""Cooperative results retain finalized output and known VM input usage."""

from dataclasses import replace

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.runtime._lifecycle import Completion
from esolangs.vm import _capture_result, complete_vm, make_vm
from tests.support.reference import REFERENCE


def test_step_exhaustion_does_not_publish_a_completed_result(monkeypatch):
    from esolangs.debugger import Debugger

    def refuse_debugger(*_args, **_kwargs):
        raise AssertionError("bounded execution must not construct a debugger")

    monkeypatch.setattr(Debugger, "__init__", refuse_debugger)
    with pytest.raises(esolangs.ExecutionCapError, match="max_steps") as caught:
        esolangs.run(REFERENCE, "+.[]", limits=esolangs.ExecutionLimits(max_steps=10))
    assert caught.value.partial_output == "\x01"
    assert caught.value.bound == "max_steps"
    result = esolangs.run(REFERENCE, "+.", limits=esolangs.ExecutionLimits(max_steps=2))
    assert result.output == "\x01"
    assert result.steps == 2


def test_an_active_vm_has_no_successful_result():
    with pytest.raises(esolangs.ArgumentError, match="requires a halted VM"):
        _capture_result(make_vm(REFERENCE, "+."))


@pytest.mark.parametrize(
    ("steps", "expected"),
    [
        (0, esolangs.ExecutionResult("", 0, 0, 0, steps=0)),
        (3, esolangs.ExecutionResult("A", 1, 1, 0, steps=3)),
    ],
)
def test_vm_completion_cap_preserves_observed_io(steps, expected):
    source = ",.[]"
    vm = make_vm(REFERENCE, source, stdin="A")
    with pytest.raises(esolangs.ExecutionCapError) as caught:
        complete_vm(vm, max_steps=steps)
    bounded = esolangs.execute(
        REFERENCE, source, stdin="A", limits=esolangs.ExecutionLimits(max_steps=steps)
    )
    assert caught.value.bound == bounded.bound == "max_steps"
    assert caught.value.observation == bounded.observation == expected
    assert caught.value.partial_output == vm.output == expected.output
    assert complete_vm(make_vm(REFERENCE, ",.", stdin="A"), max_steps=2) == "A"


def test_vm_completion_cap_keeps_custom_input_counters_unknown():
    class Custom:
        halted = False
        self_halts = True
        output = ""

        def step(self):
            self.output += "A"

    with pytest.raises(esolangs.ExecutionCapError) as caught:
        complete_vm(Custom(), max_steps=1)
    assert caught.value.observation == esolangs.ExecutionResult(
        "A", None, None, None, steps=1
    )


@pytest.mark.parametrize(("already_completed", "limit"), [(0, 3), (0, None), (2, 1)])
def test_vm_completion_fault_counts_steps_completed_in_this_call(
    already_completed, limit
):
    vm = make_vm(REFERENCE, ",.,", stdin="A")
    for _ in range(already_completed):
        vm.step()
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        complete_vm(vm, max_steps=limit)
    assert caught.value.partial_output == "A"
    assert caught.value.observation == esolangs.ExecutionResult(
        "A", 1, 1, 1, steps=2 - already_completed
    )


@pytest.mark.parametrize("observed", [False, True])
def test_vm_completion_preserves_caller_owned_fault_evidence(*, observed: bool):
    fault = esolangs.HaltError("caller fault")
    if observed:
        fault.observation = esolangs.ExecutionResult("A", None, None, None)
        fault.partial_output = "A"

    class Custom:
        halted = False
        self_halts = True
        output = ""

        def step(self):
            if self.output:
                raise fault
            self.output = "A"

    with pytest.raises(esolangs.HaltError) as caught:
        complete_vm(Custom(), max_steps=None)
    assert caught.value is fault
    expected = (
        esolangs.ExecutionResult("A", None, None, None, steps=1) if observed else None
    )
    assert fault.observation == expected


def test_custom_vm_io_fields_stay_caller_owned():
    class Custom:
        halted = True
        dumps_on_the_post_halt_step = False
        output = "custom"
        _io = object()

    result = _capture_result(Custom())
    assert result.output == "custom"
    assert result.input_position is None
    assert result.input_reads is None
    assert result.input_past_end is None
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
    assert debugger.run(limits=esolangs.ExecutionLimits(max_steps=2)) == "halted"
    result = debugger.observation
    assert result.steps == 2
    assert result.completion.kind is Completion.HALTED
    debugger.step()
    assert debugger.run(limits=esolangs.ExecutionLimits(max_steps=0)) == "halted"
    assert debugger.observation == result


def test_a_failed_halt_cannot_be_completed_by_a_peer(monkeypatch):
    from esolangs.debugger import Debugger
    from esolangs.runtime._execution import interpreter_module
    from esolangs.vm import run_until_halt, run_until_halt_or_cycle

    api = esolangs.Language(REFERENCE)
    declaration = api.catalog.languages[api.name]
    failure = esolangs.HaltError("last command failed")

    def prepare(_source, _options):
        def bind(io):
            class Machine:
                halted = False
                started = False

                def step(self):
                    if not self.started:
                        self.started = True
                    elif not self.halted:
                        self.halted = True
                        io.print_str("prefix")
                        raise failure

                def snapshot(self):
                    return self.started, self.halted

            return Machine()

        return bind

    monkeypatch.setattr(
        interpreter_module(api.name), "failed_halt", prepare, raising=False
    )
    runtime = replace(declaration.runtime, machine_preparation="failed_halt")
    scoped = esolangs.Catalog([replace(declaration, runtime=runtime)]).bind(api.name)
    first = scoped.make_debugger("+.")
    first.step()
    with pytest.raises(esolangs.HaltError) as caught:
        first.step()
    assert caught.value is failure
    expected = esolangs.ExecutionResult("prefix", 0, 0, 0, steps=1)
    assert first.observation == failure.observation == expected

    peer = Debugger(first.vm)
    assert peer.observation == replace(expected, steps=0)
    assert peer.halted
    peer.step()
    assert peer.observation == replace(expected, steps=0)
    for resume in (
        lambda: peer.run(limits=esolangs.ExecutionLimits(max_steps=0)),
        lambda: complete_vm(peer.vm, max_steps=0),
        lambda: run_until_halt(peer.vm, 1),
        lambda: run_until_halt_or_cycle(peer, 1),
    ):
        with pytest.raises(esolangs.HaltError) as caught:
            resume()
        assert caught.value is failure
        assert failure.observation == expected


def test_post_halt_completion_stays_pending_until_dump():
    from esolangs.debugger import make_debugger

    name = next(
        name
        for name, lang in LANGUAGES.items()
        if lang.parameterized
        and lang.contract.answer_mode != "termination"
        and esolangs.describe(name).dumps_on_the_post_halt_step
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


def test_caller_owned_vm_finalization_remains_local():
    from esolangs.debugger import Debugger

    class Custom:
        halted = self_halts = steppable_to_answer = dumps_on_the_post_halt_step = True
        _dump_pending = False
        output = ""
        calls = 0

        def step(self):
            self.output = "A"
            self.calls += 1

    vm = Custom()
    assert complete_vm(vm, max_steps=0) == "A"
    first, second = Debugger(vm), Debugger(vm)
    assert first.observation == esolangs.ExecutionResult("A", None, None, None, steps=0)
    limits = esolangs.ExecutionLimits(max_steps=0)
    assert first.run(limits=limits) == "halted"
    assert first.run(limits=limits) == "halted"
    assert first.observation.completion.kind is Completion.POST_HALT
    assert second.observation.completion is None
    assert vm.calls == 2
    assert second.run(limits=limits) == "halted"
    assert second.observation == first.observation
    assert vm.calls == 3


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
    with pytest.raises(esolangs.ArgumentError, match="must provide snapshot"):
        Debugger(Interrupted()).snapshot()


def test_debugger_refuses_a_step_only_object():
    from esolangs.debugger import Debugger

    class StepOnly:
        def step(self):
            pass

    with pytest.raises(esolangs.ArgumentError, match=r"vm must be a VM.*halted"):
        Debugger(StepOnly())


@pytest.mark.parametrize("drive", ["step", "run"])
def test_failed_dump_remains_unfinished_and_can_be_retried(monkeypatch, drive):
    from esolangs.debugger import Debugger, make_debugger
    from tests.support.pick import one_where

    name = one_where(
        lambda info: info.answer_mode != "termination",
        boolean_generator=True,
        parameterized=True,
        dumps_on_the_post_halt_step=True,
        steppable_to_answer=True,
    )[0]
    source = esolangs.instantiate(name, esolangs.generate(name, "01"), [1])
    debugger = make_debugger(name, source)
    assert debugger.run(limits=esolangs.ExecutionLimits(max_steps=0)) == "max_steps"
    while not debugger.halted:
        assert debugger.observation.steps < 10000
        debugger.step()
    steps = debugger.observation.steps
    other = Debugger(debugger.vm)
    machine = type(debugger.vm._machine)
    original = machine.step

    def fail(_self):
        raise esolangs.HaltError("dump failed")

    monkeypatch.setattr(machine, "step", fail)
    with pytest.raises(esolangs.HaltError, match="dump failed") as caught:
        getattr(debugger, drive)()
    assert caught.value.observation == debugger.observation
    assert debugger.observation.completion is None
    assert other.observation.completion is None
    assert debugger.observation.steps == steps
    monkeypatch.setattr(machine, "step", original)
    complete_vm(debugger.vm, max_steps=0)
    assert other.observation.completion.kind is Completion.POST_HALT
    assert debugger.observation.completion.kind is Completion.POST_HALT
    watch = debugger.watch_cell(0)
    assert debugger.run(limits=esolangs.ExecutionLimits(max_steps=0)) == "halted"
    assert watch == []
    assert debugger.observation.completion.kind is Completion.POST_HALT
    assert debugger.observation.steps == steps
    assert esolangs.read_answer(name, debugger.observation.output) == "1"


def test_error_observation_annotation_resolves_public_result_type():
    from typing import get_type_hints

    assert get_type_hints(esolangs.EsolangError)["observation"] == (
        esolangs.ExecutionResult | None
    )
