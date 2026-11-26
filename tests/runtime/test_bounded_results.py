"""Cooperative results retain finalized output and known VM input usage."""

from dataclasses import replace
from itertools import product

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.runtime._lifecycle import Completion
from esolangs.runtime._vm_adapter import _capture_result
from esolangs.vm import complete_vm, make_vm
from tests.support.reference import REFERENCE


def test_step_exhaustion_does_not_publish_a_completed_result(monkeypatch):
    from esolangs.debugger import Debugger

    def refuse_debugger(*_args, **_kwargs):
        raise AssertionError("bounded execution must not construct a debugger")

    monkeypatch.setattr(Debugger, "__init__", refuse_debugger)
    with pytest.raises(esolangs.ExecutionCapError, match="max_steps") as caught:
        esolangs.run(
            REFERENCE, "+.[]", limits=esolangs.ExecutionLimits(max_steps=10)
        ).unwrap()
    assert caught.value.partial_output == "\x01"
    assert caught.value.bound == "max_steps"
    result = esolangs.run(
        REFERENCE, "+.", limits=esolangs.ExecutionLimits(max_steps=2)
    ).unwrap()
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
    from esolangs.debugger import make_debugger

    source = ",.[]"
    bounded = esolangs.run(
        REFERENCE, source, stdin="A", limits=esolangs.ExecutionLimits(max_steps=steps)
    )
    for make in (make_vm, make_debugger):
        live = make(REFERENCE, source, stdin="A")
        with pytest.raises(esolangs.ExecutionCapError) as caught:
            complete_vm(live, max_steps=steps)
        assert caught.value.bound == bounded.bound == "max_steps"
        assert caught.value.observation == bounded.observation == expected
        assert caught.value.partial_output == live.output == expected.output
        assert complete_vm(make(REFERENCE, ",.", stdin="A"), max_steps=2) == "A"


def test_vm_completion_cap_keeps_custom_input_counters_unknown():
    from esolangs.debugger import Debugger

    class Custom:
        halted = False
        self_halts = True
        steppable_to_answer = True
        dumps_on_the_post_halt_step = False
        output = ""

        def step(self):
            self.output += "A"

    for live in (Custom(), Debugger(Custom())):
        with pytest.raises(esolangs.ExecutionCapError) as caught:
            complete_vm(live, max_steps=1)
        assert caught.value.observation == esolangs.ExecutionResult(
            "A", None, None, None, steps=1
        )


@pytest.mark.parametrize(("already_completed", "limit"), [(0, 3), (0, None), (2, 1)])
def test_vm_completion_fault_counts_steps_completed_in_this_call(
    already_completed, limit
):
    from esolangs.debugger import make_debugger

    for make in (make_vm, make_debugger):
        vm = make(REFERENCE, ",.,", stdin="A")
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
    from esolangs.debugger import Debugger

    fault = esolangs.HaltError("caller fault")
    if observed:
        fault.observation = esolangs.ExecutionResult("A", None, None, None)
        fault.partial_output = "A"

    class Custom:
        halted = False
        self_halts = True
        steppable_to_answer = True
        dumps_on_the_post_halt_step = False
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

    with pytest.raises(esolangs.HaltError) as caught:
        complete_vm(Debugger(Custom()), max_steps=None)
    assert caught.value is fault
    assert fault.observation == esolangs.ExecutionResult("A", None, None, None, steps=1)


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

    limits = esolangs.ExecutionLimits(max_steps=0)
    for peer in (Debugger(first.vm), Debugger(first), Debugger(Debugger(first))):
        assert peer.observation == replace(expected, steps=0)
        assert peer.halted
        peer.step()
        assert peer.observation == replace(expected, steps=0)
        for resume in (
            lambda vm: vm.run(limits=limits),
            lambda vm: complete_vm(vm, max_steps=0),
            lambda vm: run_until_halt(vm, limit=0),
            lambda vm: run_until_halt_or_cycle(vm, limit=0),
        ):
            with pytest.raises(esolangs.HaltError) as caught:
                resume(peer)
            assert caught.value is failure
            assert failure.observation == expected

    control = Debugger(Debugger(api.make_debugger("+.")))
    assert complete_vm(control, max_steps=2) == "\x01"
    assert control.observation.completion.kind is Completion.HALTED
    assert control.observation.steps == 2
    assert run_until_halt(control, limit=0)
    assert run_until_halt_or_cycle(control, limit=0)

    _check_switched_terminal_halt(lambda: api.make_vm("+."), first, failure)
    _check_halt_read_fault_evidence(api, monkeypatch)
    _check_caller_halt_read_evidence()
    _check_observer_failure_evidence(api, monkeypatch)
    _check_raw_watch_preserves_failure()


def _check_halt_read_fault_evidence(api, monkeypatch):
    from esolangs.debugger import Debugger
    from esolangs.runtime._execution import interpreter_module

    original = esolangs.HaltError("command failed")
    reads = []
    terminal_checks = []
    mode = "typed"
    foreign = esolangs.HaltError("foreign halt inspection failed")
    foreign.observation = esolangs.ExecutionResult("inner", 2, 1, 0, steps=7)
    foreign.partial_output = "inner"

    class Machine:
        finished = False
        checks = 0

        def __init__(self, io):
            self.io = io

        @property
        def halted(self):
            self.checks += 1
            if self.finished:
                terminal_checks.append(self.checks)
                if mode.startswith("final_"):
                    if len(terminal_checks) != 2:
                        return True
                    if mode == "final_foreign":
                        reads.append(foreign)
                        raise foreign
            if (self.finished and mode != "valid") or (
                mode == "before_step" and self.checks == 2
            ):
                error_type = ValueError if mode.endswith("bare") else esolangs.HaltError
                error = error_type("halt inspection failed")
                reads.append(error)
                raise error
            return self.finished

        def step(self):
            self.io.print_char(chr(self.io.input_char()))
            self.finished = True
            if mode == "command":
                raise original

    monkeypatch.setattr(
        interpreter_module(api.name),
        "halt_inspection",
        lambda *_args: Machine,
        raising=False,
    )
    declaration = api.catalog.languages[api.name]
    runtime = replace(declaration.runtime, machine_preparation="halt_inspection")
    scoped = esolangs.Catalog([replace(declaration, runtime=runtime)]).bind(api.name)
    limits = esolangs.ExecutionLimits(max_steps=2)
    expected = esolangs.ExecutionResult("A", 1, 1, 0, steps=1)
    for mode in ("typed", "bare"):
        error_type = esolangs.ProgramError if mode == "bare" else esolangs.HaltError
        calls = (
            lambda: scoped.run("+.", stdin="A", limits=limits).unwrap(),
            lambda: Debugger(scoped.make_debugger("+.", stdin="A")).run(limits=limits),
            lambda: complete_vm(scoped.make_vm("+.", stdin="A"), max_steps=2),
        )
        for drive in calls:
            reads.clear()
            with pytest.raises(error_type, match="halt inspection") as caught:
                drive()
            if mode == "bare":
                assert reads == [caught.value.__cause__]
            else:
                assert reads == [caught.value]
            assert caught.value.partial_output == "A"
            assert caught.value.observation == expected

    plan = scoped.prepare("+.")
    for mode in ("final_typed", "final_bare", "final_foreign"):
        for execute in (
            lambda: scoped.run("+.", stdin="A", limits=limits),
            lambda: plan.run(stdin="A", limits=limits),
        ):
            reads.clear()
            terminal_checks.clear()
            outcome = execute()
            assert outcome.observation == expected
            assert len(terminal_checks) == 2
            if mode == "final_bare":
                assert outcome.status == "rejected"
                assert isinstance(outcome.error, esolangs.ProgramError)
                assert reads == [outcome.error.__cause__]
            else:
                assert outcome.status == "fault"
                assert reads == [outcome.error]
            if mode == "final_foreign":
                assert outcome.error is foreign
                assert foreign.observation.output == foreign.partial_output == "inner"
                assert foreign.observation.steps == 7
            else:
                assert outcome.error.observation == expected
                assert outcome.error.partial_output == "A"

    mode = "before_step"
    with pytest.raises(esolangs.HaltError, match="halt inspection") as caught:
        scoped.make_debugger("+.", stdin="A").run(limits=limits)
    assert caught.value.observation == esolangs.ExecutionResult("", 0, 0, 0, steps=0)

    mode = "command"
    reads.clear()
    with pytest.raises(esolangs.HaltError, match="command failed") as caught:
        scoped.make_vm("+.", stdin="A").step()
    assert caught.value is original
    assert original.observation == replace(expected, steps=None)
    assert len(reads) == 1

    mode = "valid"
    completed = scoped.run("+.", stdin="A", limits=limits).unwrap()
    assert completed == replace(expected, completion=completed.completion)
    assert completed.completion.kind is Completion.HALTED
    assert plan.run(stdin="A", limits=limits).unwrap() == completed
    debug = scoped.make_debugger("+.", stdin="A")
    assert debug.run(limits=limits) == "halted"
    assert debug.observation == completed
    assert complete_vm(scoped.make_vm("+.", stdin="A"), max_steps=2) == "A"


def _check_caller_halt_read_evidence():
    from esolangs.debugger import Debugger

    original = esolangs.HaltError("foreign observation")
    expected = esolangs.ExecutionResult("foreign", 1, 1, 0, steps=7)
    original.observation = expected
    original.partial_output = expected.output

    class Custom:
        output = "outer"
        self_halts = steppable_to_answer = True
        dumps_on_the_post_halt_step = False

        @property
        def halted(self):
            raise original

        def step(self):
            pytest.fail("the failed halt inspection must not take a step")

    live = Debugger(Custom())
    with pytest.raises(esolangs.HaltError, match="foreign observation") as caught:
        live.run(limits=esolangs.ExecutionLimits(max_steps=0))
    assert caught.value is original
    assert original.observation is expected
    assert original.partial_output == expected.output


def _check_observer_failure_evidence(api, monkeypatch):
    from esolangs.debugger import Debugger
    from esolangs.runtime._execution import interpreter_module
    from esolangs.vm import (
        run_until_halt_or_ancestor,
        run_until_halt_or_cycle,
        run_until_halt_or_growth,
        run_until_halt_or_value_growth,
    )

    mode = "snapshot"
    resumed_steps = 2
    errors = []
    foreign = esolangs.HaltError("foreign snapshot fault")
    foreign.observation = esolangs.ExecutionResult("inner", 2, 1, 0, steps=7)
    foreign.partial_output = "inner"

    class Machine:
        index = 0
        frames = (0,)
        tape = values = (0, 0, 0)
        clamp_slack = None

        @property
        def ip(self):
            return self.index

        key = ptr = ip

        def input_position(self):
            return min(self.index, 1)

        def frame_entry_key(self, frame):
            return frame

        def __init__(self, io):
            self.io = io

        @property
        def halted(self):
            return self.index >= {"watch": 1, "resumed_watch": resumed_steps}.get(
                mode, 2
            )

        def step(self):
            if self.index == 1 and mode == "command_fault":
                self.fail("command failed")
            if not self.index:
                self.io.print_char(chr(self.io.input_char()))
            self.index += 1

        def fail(self, message):
            error = esolangs.HaltError(message)
            errors.append(error)
            raise error

        def snapshot(self):
            if self.index and mode == "snapshot":
                self.fail("snapshot read failed")
            if self.index and mode == "foreign":
                raise foreign
            return (self.index,)

        @property
        def memory(self):
            if (self.index and mode == "watch") or (
                mode == "resumed_watch" and self.index == resumed_steps
            ):
                self.fail("watch read failed")
            return [self.index]

    monkeypatch.setattr(
        interpreter_module(api.name),
        "failing_observer",
        lambda *_args: Machine,
        raising=False,
    )
    declaration = api.catalog.languages[api.name]
    runtime = replace(declaration.runtime, machine_preparation="failing_observer")
    contract = replace(
        declaration.contract,
        answer_mode="termination",
        answer_values=("halts", "diverges"),
    )
    scoped = esolangs.Catalog(
        [replace(declaration, runtime=runtime, contract=contract)]
    ).bind(api.name)
    artifact = scoped.from_source("+.")
    limits = esolangs.ExecutionLimits(max_steps=2)
    expected = esolangs.ExecutionResult("1", 1, 1, 0, steps=1)
    for invoke in (
        lambda: run_until_halt_or_cycle(scoped.make_vm(artifact, stdin="1"), limit=2),
        lambda: run_until_halt_or_cycle(
            scoped.make_debugger(artifact, stdin="1"), limit=2
        ),
        lambda: scoped.evaluate(artifact, [1], limits=limits),
    ):
        with pytest.raises(esolangs.HaltError, match="snapshot read") as caught:
            invoke()
        assert caught.value is errors[-1]
        assert caught.value.partial_output == "1"
        assert caught.value.observation == expected

    mode = "foreign"
    live = scoped.make_debugger(artifact, stdin="1")
    with pytest.raises(esolangs.HaltError, match="foreign snapshot") as caught:
        run_until_halt_or_cycle(live, limit=2)
    assert caught.value is foreign
    assert foreign.observation == esolangs.ExecutionResult("inner", 2, 1, 0, steps=7)
    assert foreign.partial_output == "inner"

    mode = "watch"
    for nested in (False, True):
        inner = scoped.make_debugger(artifact, stdin="1")
        history = inner.watch_cell(0)
        live = Debugger(inner) if nested else inner
        with pytest.raises(esolangs.HaltError, match="watch read") as caught:
            complete_vm(live, max_steps=2)
        assert caught.value is errors[-1]
        assert caught.value.observation == expected
        assert caught.value.partial_output == "1"
        assert live.observation.steps == inner.observation.steps == 1
        assert live.observation.completion.kind is Completion.HALTED
        assert not history
        assert live.run(limits=esolangs.ExecutionLimits(max_steps=0)) == "halted"

    lap_proofs = (
        run_until_halt_or_ancestor,
        run_until_halt_or_growth,
        run_until_halt_or_value_growth,
    )
    mode = "resumed_watch"
    for invoke, resumed_steps, nested in product(
        (complete_vm, run_until_halt_or_cycle, *lap_proofs),
        (2, 3),
        (False, True),
    ):
        inner = scoped.make_debugger(artifact, stdin="1")
        live = Debugger(inner) if nested else inner
        _check_resumed_watch(invoke, live, inner, expected, errors, resumed_steps)

    mode = "command_fault"
    for proof in (run_until_halt_or_cycle, *lap_proofs):
        live = scoped.make_debugger(artifact, stdin="1")
        live.step()
        with pytest.raises(esolangs.HaltError, match="command failed") as caught:
            proof(live, 2)
        assert caught.value is errors[-1]
        assert caught.value.observation == expected
        assert live.observation.steps == 1
        assert not live.halted

    mode = "valid"
    for proof in lap_proofs:
        live = scoped.make_debugger(artifact, stdin="1")
        live.step()
        assert proof(live, 1) is True
        assert live.output == "1"
        assert live.observation.steps == 2

    live = scoped.make_debugger(artifact, stdin="1")
    assert run_until_halt_or_cycle(live, limit=2)
    assert live.observation == replace(
        expected, steps=2, completion=live.observation.completion
    )
    live = scoped.make_debugger(artifact, stdin="1")
    history = live.watch_cell(0)
    assert live.run(limits=limits) == "halted"
    assert history == [1, 2]


def _check_resumed_watch(invoke, live, inner, expected, errors, resumed_steps):
    live.step()
    inner.watch_cell(0)
    with pytest.raises(esolangs.HaltError, match="watch read") as caught:
        invoke(live, 2)
    assert caught.value is errors[-1]
    assert caught.value.observation == replace(expected, steps=resumed_steps - 1)
    assert live.observation.steps == resumed_steps
    assert live.observation.completion.kind is Completion.HALTED


def _check_raw_watch_preserves_failure():
    from esolangs.debugger import Debugger

    class Custom:
        halted = False
        self_halts = steppable_to_answer = True
        dumps_on_the_post_halt_step = False

        def step(self):
            self.halted = True

        @property
        def memory(self):
            raise raw_error

        @property
        def output(self):
            raise RuntimeError("caller output unavailable")

    for observation in (None, esolangs.ExecutionResult("foreign", 2, 1, 0, steps=4)):
        raw_error = esolangs.HaltError("raw watch failed")
        if observation is not None:
            raw_error.observation = observation
            raw_error.partial_output = observation.output
        inner = Debugger(Custom())
        inner.watch_cell(0)
        live = Debugger(inner)
        with pytest.raises(esolangs.HaltError, match="raw watch failed") as caught:
            live.run(limits=esolangs.ExecutionLimits(max_steps=1))
        assert caught.value is raw_error
        assert raw_error.observation is observation
        assert live.halted


def test_post_halt_completion_stays_pending_until_dump():
    from esolangs.debugger import Debugger, make_debugger

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
    nested = Debugger(Debugger(debugger))
    assert nested.observation == replace(before, steps=0)
    assert before.completion is None
    debugger.step()
    assert debugger.observation.steps == before.steps
    assert debugger.observation.completion.kind is Completion.POST_HALT
    assert esolangs.read_answer(name, debugger.observation.output) == "1"
    assert nested.observation == replace(debugger.observation, steps=0)
    assert complete_vm(nested, max_steps=0) == debugger.output
    assert nested.observation == replace(debugger.observation, steps=0)

    expected = debugger.observation
    limits = esolangs.ExecutionLimits(max_steps=expected.steps)
    for wrapped in (False, True):
        receiver = make_debugger(name, source)
        live = Debugger(receiver) if wrapped else receiver
        assert live.run(limits=limits) == "halted"
        assert live.observation == expected

        receiver.vm = make_vm(name, source)
        assert live.observation.completion is None
        assert live.run(limits=limits) == "halted"
        assert live.observation == replace(expected, steps=expected.steps * 2)
        assert Debugger(receiver.vm).observation == replace(expected, steps=0)


def test_caller_owned_vm_finalization_remains_local():
    from esolangs.debugger import Debugger

    class Custom:
        halted = self_halts = steppable_to_answer = dumps_on_the_post_halt_step = True
        _dump_pending = False
        calls = 0
        output = ""

        @property
        def memory(self):
            return [1]

        def step(self):
            self.output = "A"
            self.calls += 1

    vm = Custom()
    assert complete_vm(vm, max_steps=0) == "A"
    first, second = Debugger(vm), Debugger(vm)
    assert first.observation == esolangs.ExecutionResult("A", None, None, None, steps=0)
    limits = esolangs.ExecutionLimits(max_steps=0)
    history = first.watch_cell(0)
    assert first.run(limits=limits) == "halted"
    assert first.run(limits=limits) == "halted"
    assert first.observation.completion.kind is Completion.POST_HALT
    assert second.observation.completion is None
    assert vm.calls == 2

    nested = Debugger(Debugger(first))
    assert nested.observation == first.observation
    for live in (first, nested):
        assert complete_vm(live, max_steps=0) == "A"
        assert live.run(limits=limits) == "halted"
    assert history == [1]
    assert vm.calls == 2

    assert second.run(limits=limits) == "halted"
    assert second.observation == first.observation
    assert vm.calls == 3

    for wrapped in (False, True):
        raw = Custom()
        receiver = Debugger(raw)
        live = Debugger(receiver) if wrapped else receiver
        assert live.run(limits=limits) == "halted"
        before = live.observation
        receiver.vm = Debugger(Debugger(raw))
        assert live.observation == before
        assert complete_vm(live, max_steps=0) == "A"
        assert live.run(limits=limits) == "halted"
        assert raw.calls == 1

        receiver.vm = Custom()
        assert live.observation == replace(before, output="", completion=None)
        assert live.run(limits=limits) == "halted"
        assert live.observation == before
        assert receiver.vm.calls == 1

    class RewrapAfterDump(Debugger):
        def __init__(self, raw):
            super().__init__(raw)
            self.raw = raw

        def step(self):
            super().step()
            if self.vm is self.raw:
                self.vm = Debugger(self.raw)

    raw = Custom()
    rewrapped = Debugger(RewrapAfterDump(raw))
    assert complete_vm(rewrapped, max_steps=0) == "A"
    assert rewrapped.observation.completion.kind is Completion.POST_HALT
    assert raw.calls == 1

    class RestartableDump(Custom):
        def step(self):
            if self.halted:
                super().step()
            else:
                self.halted = True

    raw = RestartableDump()
    restarted = Debugger(raw)
    assert restarted.run(limits=limits) == "halted"
    assert raw.calls == 1
    raw.halted = False
    assert complete_vm(restarted, max_steps=1) == "A"
    assert restarted.observation.steps == 1
    assert restarted.observation.completion.kind is Completion.POST_HALT
    assert restarted.run(limits=limits) == "halted"
    assert raw.calls == 2

    class RetryDump(Custom):
        output = ""

        def step(self):
            if not self.output:
                self.output = "pre"
                raise esolangs.HaltError("temporary dump failure")
            self.output += "done"

    retry = Debugger(Custom())
    assert retry.run(limits=limits) == "halted"
    retry.vm = RetryDump()
    with pytest.raises(esolangs.HaltError, match="temporary dump") as caught:
        retry.run(limits=limits)
    assert caught.value.observation == esolangs.ExecutionResult(
        "pre", None, None, None, steps=0
    )
    assert retry.observation.completion is None
    nested_retry = Debugger(retry)
    assert complete_vm(nested_retry, max_steps=0) == "predone"
    assert nested_retry.run(limits=limits) == "halted"
    assert retry.output == "predone"
    assert retry.observation.completion.kind is Completion.POST_HALT
    assert retry.observation.steps == 0

    _check_caller_owned_failed_halt()


def _check_caller_owned_failed_halt():
    from esolangs.debugger import Debugger
    from esolangs.vm import run_until_halt, run_until_halt_or_cycle

    class Custom:
        halted = False
        self_halts = steppable_to_answer = True
        dumps_on_the_post_halt_step = False
        output = ""

        def __init__(self, error=None):
            self.error = error

        def step(self):
            if self.halted:
                return
            self.halted = True
            if self.error is not None:
                self.output = "prefix"
                raise self.error
            self.output = "done"

        def snapshot(self):
            return self.halted

    original = esolangs.HaltError("failed active command")
    inner = Debugger(Custom(original))
    outer = Debugger(inner)
    with pytest.raises(esolangs.HaltError) as caught:
        outer.step()
    partial = esolangs.ExecutionResult("prefix", None, None, None, steps=0)
    assert caught.value is original
    assert original.observation == inner.observation == outer.observation == partial
    limits = esolangs.ExecutionLimits(max_steps=0)
    resumes = (
        lambda vm: vm.run(limits=limits),
        lambda vm: complete_vm(vm, max_steps=0),
        lambda vm: run_until_halt(vm, limit=0),
        lambda vm: run_until_halt_or_cycle(vm, limit=0),
    )
    observation = original.observation
    for rewrap in (False, True):
        if rewrap:
            inner.vm = Debugger(Debugger(inner.vm))
        for live in (inner, outer, Debugger(outer)):
            live.step()  # An idle step is still harmless.
            for resume in resumes:
                with pytest.raises(esolangs.HaltError) as caught:
                    resume(live)
                assert caught.value is original
                assert original.observation is observation
                assert live.observation == partial

    _check_switched_terminal_halt(Custom, outer, original)

    # An explicit replacement cannot inherit the previous VM's failure.
    replacement = Custom()
    replacement.step()
    inner.vm = replacement
    for live in (inner, outer):
        assert live.run(limits=limits) == "halted"
        assert complete_vm(live, max_steps=0) == "done"
        assert live.observation.completion.kind is Completion.HALTED

    class Replacing(Custom):
        def step(self):
            try:
                super().step()
            finally:
                inner.vm = replacement

    inner = Debugger(Replacing(original))
    outer = Debugger(inner)
    with pytest.raises(esolangs.HaltError) as caught:
        outer.step()
    assert caught.value is original
    assert original.observation == partial
    assert outer.run(limits=limits) == "halted"
    assert complete_vm(outer, max_steps=0) == "done"
    assert outer.observation.completion.kind is Completion.HALTED

    # Repairing the same raw VM before retrying can take a new active step.
    raw = Custom(original)
    live = Debugger(raw)
    with pytest.raises(esolangs.HaltError):
        live.step()
    raw.error = None
    raw.halted = False
    assert live.run(limits=esolangs.ExecutionLimits(max_steps=1)) == "halted"
    assert live.output == "done"
    assert live.observation.completion.kind is Completion.HALTED
    assert live.observation.steps == 1


def _check_switched_terminal_halt(fresh, failed, failure):
    from esolangs.debugger import Debugger
    from esolangs.vm import run_until_halt

    class SwitchAfterStep(Debugger):
        def __init__(self, vm, target):
            super().__init__(vm)
            self.target = target

        def step(self):
            super().step()
            self.vm = self.target

    class Watched:
        halted = False
        self_halts = steppable_to_answer = True
        dumps_on_the_post_halt_step = False
        output = ""

        def step(self):
            self.output = "active"

        @property
        def memory(self):
            self.live.vm = self.target
            return [7]

    class PendingDump:
        halted = self_halts = steppable_to_answer = dumps_on_the_post_halt_step = True
        output = ""

        def step(self):
            self.output += "dumped"

    limits = esolangs.ExecutionLimits(max_steps=1)
    original = failure.observation
    clean = fresh()
    assert run_until_halt(clean, limit=2)
    for target in (failed, clean):
        raw = Watched()
        raw.target = target
        watch = Debugger(raw)
        raw.live = watch
        history = watch.watch_cell(0)
        pending = PendingDump()
        cases = (
            (run_until_halt, SwitchAfterStep(fresh(), target), True, 1),
            (complete_vm, SwitchAfterStep(fresh(), target), target.output, 1),
            (lambda vm, _cap: vm.run(limits=limits), watch, "halted", 1),
            (complete_vm, SwitchAfterStep(pending, target), target.output, 0),
        )
        for invoke, live, result, steps in cases:
            if target is failed:
                with pytest.raises(esolangs.HaltError) as caught:
                    invoke(live, steps)
                assert caught.value is failure
                assert failure.observation is original
                assert live.observation.completion is None
            else:
                assert invoke(live, steps) == result
                assert live.observation.completion.kind is Completion.HALTED
            assert live.vm is target
            assert live.observation.steps == steps
        assert history == [7]
        assert pending.output == "dumped"


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
