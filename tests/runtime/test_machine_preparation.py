"""Declared construction owns fresh state and preserves source-step behavior."""

from dataclasses import replace
from io import StringIO
from types import SimpleNamespace

import pytest

import esolangs
from esolangs import vm
from esolangs.languages.brainfuck.interpreter import _Machine, prepare_machine
from esolangs.registry import Catalog
from esolangs.results import Completion, CompletionReport
from tests.support.reference import REFERENCE


def test_declared_preparation_needs_no_private_constructor(monkeypatch):
    calls = []
    monkeypatch.setattr(_Machine, "completion", Completion.POST_HALT, raising=False)
    monkeypatch.setattr(_Machine, "ip_shape", "opaque", raising=False)
    monkeypatch.setattr(_Machine, "surprise", property(lambda _self: 99), raising=False)

    def prepare(source, options):
        calls.append((source, dict(options)))
        return prepare_machine(source, options)

    monkeypatch.setattr(
        vm,
        "interpreter_module",
        lambda _name, **_options: SimpleNamespace(prepare_machine=prepare),
    )
    machine = vm.make_vm("brainfuck", ",+.", stdin="A")
    assert calls == [(",+.", {})]
    assert machine.ip == 0
    assert machine.ip_shape == "offset"
    assert not machine.dumps_on_the_post_halt_step
    assert machine.views == (("ind", "0"), ("ptr", "0"), ("tape", "(0,)"))
    machine.step()
    assert machine.ip == 1
    machine.step()
    machine.step()
    assert machine.halted
    assert machine.output == "B"


def test_preparation_refuses_wrong_shapes_and_options():
    with pytest.raises(TypeError, match="text source"):
        prepare_machine(["+"], {})
    with pytest.raises(TypeError, match="no runtime options"):
        prepare_machine("+", {"rng": object()})


def test_missing_runtime_hooks_are_public_program_errors() -> None:
    api = esolangs.Language(REFERENCE)
    record = api.catalog.languages[api.name]

    class PretendName:
        @property
        def __class__(self) -> type[str]:
            return str

        def isidentifier(self) -> bool:
            return True

    class HookName(str):
        def __str__(self) -> str:
            raise AssertionError("stringified the runtime name override")

        def isidentifier(self) -> bool:
            raise AssertionError("checked the hook name's overridden identifier")

        def __hash__(self) -> int:
            raise AssertionError("looked up the hook name's override")

    hooks = {}
    for key in ("machine_preparation", "completion_entrypoint"):
        with pytest.raises(ValueError, match=f"runtime {key} must name"):
            replace(record.runtime, **{key: PretendName()})
        hooks[key] = HookName(getattr(record.runtime, key))
    with pytest.raises(ValueError, match="runtime interpreter must be a string"):
        replace(record.runtime, interpreter=PretendName())
    assert record.runtime.interpreter is not None
    runtime = replace(
        record.runtime, interpreter=HookName(record.runtime.interpreter), **hooks
    )
    assert type(runtime.interpreter) is str
    assert all(type(getattr(runtime, key)) is str for key in hooks)
    wrapped = Catalog([replace(record, runtime=runtime)]).bind(api.name)
    assert wrapped.run("+.").unwrap().output == "\x01"
    debugger = wrapped.make_debugger("+.")
    assert debugger.run(limits=esolangs.ExecutionLimits(max_steps=2)) == "halted"
    assert debugger.output == "\x01"

    no_prepare = replace(record.runtime, machine_preparation="absent_preparation")
    scoped = Catalog([replace(record, runtime=no_prepare)]).bind(api.name)
    assert scoped.run("+.").unwrap().output == "\x01"
    for operation in (scoped.prepare, scoped.make_vm, scoped.make_debugger):
        with pytest.raises(esolangs.ProgramError, match="absent_preparation"):
            operation("+.")
    no_completion = replace(record.runtime, completion_entrypoint="absent_completion")
    scoped = Catalog([replace(record, runtime=no_completion)]).bind(api.name)
    assert isinstance(scoped.run("+.").error, esolangs.ProgramError)
    with pytest.raises(esolangs.ProgramError, match="absent_completion"):
        scoped.run("+.").unwrap()
    assert (
        scoped.run("+.", limits=esolangs.ExecutionLimits(max_steps=2)).unwrap().output
        == "\x01"
    )
    prepared = scoped.prepare("+.")

    class ManagedInput(StringIO):
        bindings = 0

        @property
        def read(self):
            self.bindings += 1
            return super().read

    for limits in (None, esolangs.ExecutionLimits(preparation_timeout=2)):
        stdin = ManagedInput("unread")
        with pytest.raises(esolangs.ProgramError, match="absent_completion"):
            prepared.run(stdin=stdin, limits=limits).unwrap()
        assert stdin.bindings == 1
        assert stdin.tell() == 0
        with pytest.raises(esolangs.ArgumentError, match="stdin must"):
            prepared.run(stdin=object(), limits=limits).unwrap()
    assert (
        prepared.run(limits=esolangs.ExecutionLimits(max_steps=2)).unwrap().output
        == "\x01"
    )


@pytest.mark.parametrize("hook", ["completion_entrypoint", "machine_preparation"])
def test_native_prepared_runs_apply_the_declared_hooks(monkeypatch, hook) -> None:
    from esolangs.registry import _table
    from esolangs.runtime._execution import interpreter_module
    from esolangs.runtime._lifecycle import HALTED_REPORT
    from esolangs.runtime._machine import RuntimePlan

    api = esolangs.Language(REFERENCE)
    declaration = api.catalog.languages[api.name]
    interpreter = interpreter_module(api.name)

    def alternate(_code, io):
        io.print_str("custom: " + chr(io.input_char()))
        return HALTED_REPORT

    def prepare(source, options):
        installed = prepare_machine(source, options)
        return RuntimePlan(installed.machine, lambda io: alternate(source, io))

    native = hook == "completion_entrypoint"
    monkeypatch.setattr(
        interpreter, "alternate_hook", alternate if native else prepare, raising=False
    )
    runtime = replace(declaration.runtime, **{hook: "alternate_hook"})
    catalog = Catalog([replace(declaration, runtime=runtime)])
    scoped = catalog.bind(api.name)
    artifact = scoped.from_source(",.")
    prepared = scoped.prepare(artifact)
    result = prepared.run(stdin="A").unwrap()
    assert result == scoped.run(artifact, stdin="A").unwrap()
    assert result.output == ("custom: A" if native else "A")
    assert prepared.evaluate([1]) == artifact.evaluate([1], catalog=scoped.catalog)
    assert (
        prepared.run(stdin="A", limits=esolangs.ExecutionLimits(max_steps=2))
        .unwrap()
        .output
        == "A"
    )
    monkeypatch.setattr(_table, "CATALOG", catalog)
    assert esolangs.prepare(api.name, artifact).run(stdin="A").unwrap() == result


def test_preparation_requires_a_callable_factory(monkeypatch) -> None:
    from esolangs.runtime._execution import interpreter_module

    api = esolangs.Language(REFERENCE)
    runtime = api.catalog.languages[api.name].runtime
    interpreter = interpreter_module(api.name)
    monkeypatch.setattr(interpreter, runtime.machine_preparation, lambda *_args: None)
    for operation in (api.prepare, api.make_vm):
        with pytest.raises(esolangs.InterpreterLimitError, match="no machine factory"):
            operation("+.")

    def prepare(_source, _options):
        def initialize(io):
            io.print_char(chr(io.input_char()))
            return machine

        return initialize

    monkeypatch.setattr(interpreter, "custom_initialize", prepare, raising=False)
    declaration = api.catalog.languages[api.name]
    runtime = replace(runtime, machine_preparation="custom_initialize")
    scoped = Catalog([replace(declaration, runtime=runtime)]).bind(api.name)
    source = "+."
    prepared = scoped.prepare(source)
    expected = esolangs.ExecutionResult("A", 1, 1, 0)
    limits = esolangs.ExecutionLimits(max_steps=0)
    machine = None
    for create in (scoped.make_vm, scoped.make_debugger):
        with pytest.raises(
            esolangs.InterpreterLimitError, match="machine factory result"
        ) as caught:
            create(source, stdin="A")
        assert caught.value.observation == expected
        assert caught.value.partial_output == "A"
    for outcome in (
        scoped.run(source, stdin="A", limits=limits),
        prepared.run(stdin="A", limits=limits),
    ):
        assert isinstance(outcome.error, esolangs.InterpreterLimitError)
        assert outcome.observation == outcome.error.observation == expected
        assert outcome.error.partial_output == "A"

    class LazyHalt:
        observations = 0

        @property
        def halted(self):
            self.observations += 1
            return True

        def step(self):
            pytest.fail("stepped an already halted machine")

    machine = LazyHalt()
    assert scoped.make_vm(source, stdin="A").output == "A"
    assert prepared.make_debugger(stdin="A").output == "A"
    assert machine.observations == 0

    class Forwarder:
        def __init__(self, inner):
            self.inner = inner

        def __getattr__(self, name):
            return getattr(self.inner, name)

    machine = Forwarder(machine)
    result = prepared.run(stdin="A", limits=limits).unwrap()
    assert result == replace(
        expected, completion=CompletionReport(Completion.HALTED), steps=0
    )

    class RefusedStep:
        @property
        def step(self):
            raise original

    original = esolangs.ArgumentError("custom step binding refused")
    machine = RefusedStep()
    with pytest.raises(esolangs.ArgumentError, match="custom step binding") as caught:
        scoped.make_vm(source, stdin="A")
    assert caught.value is original
    assert original.observation == expected

    active = esolangs.ExecutionLimits(max_steps=1)
    for fields in ({}, {"snapshot": 0}):
        machine = SimpleNamespace(halted=False, step=lambda: None, **fields)
        debug = prepared.make_debugger(stdin="A")
        assert debug.run(limits=active) == "max_steps"
        outcome = prepared.run(stdin="A", limits=active)
        assert outcome.bound == "max_steps"
        assert outcome.observation == debug.observation == replace(expected, steps=1)
        with pytest.raises(esolangs.ArgumentError, match="must provide snapshot"):
            debug.snapshot()
        for live in (debug, debug.vm):
            with pytest.raises(TypeError, match=r"callable snapshot"):
                vm.run_until_halt_or_cycle(live, limit=1)
        assert debug.observation.steps == 1

    machine.halted = True
    assert vm.run_until_halt_or_cycle(debug, limit=0)
    machine.halted = False

    refused = esolangs.ArgumentError("snapshot callback refused")

    def snapshot():
        raise refused

    machine.snapshot = snapshot
    with pytest.raises(esolangs.ArgumentError, match="snapshot callback") as caught:
        vm.run_until_halt_or_cycle(debug, limit=1)
    assert caught.value is refused
    assert debug.observation.steps == 1

    contract = replace(
        declaration.contract,
        answer_mode="termination",
        answer_values=("halts", "diverges"),
    )
    termination = Catalog(
        [replace(declaration, runtime=runtime, contract=contract)]
    ).bind(api.name)
    artifact = termination.from_source(source)
    for fields, diagnostic in (
        ({}, "callable snapshot"),
        ({"snapshot": 0}, "callable snapshot"),
        ({"snapshot": lambda: [0]}, "hashable state"),
        ({"snapshot": lambda: ([0],)}, "hashable state"),
    ):
        machine = SimpleNamespace(halted=False, step=lambda: None, **fields)
        with pytest.raises(esolangs.InterpreterLimitError, match=diagnostic) as caught:
            artifact.evaluate([1], limits=active, catalog=termination.catalog)
        assert caught.value.observation == esolangs.ExecutionResult(
            "1", 1, 1, 0, steps=0
        )
        assert caught.value.partial_output == "1"
        if diagnostic == "hashable state":
            debug = prepared.make_debugger(stdin="A")
            for live in (debug, debug.vm):
                with pytest.raises(esolangs.ArgumentError, match=diagnostic):
                    live.snapshot()
                with pytest.raises(TypeError, match=diagnostic):
                    vm.run_until_halt_or_cycle(live, limit=1)
            assert debug.run(limits=active) == "max_steps"

    machine.snapshot = lambda: (0,)
    debug = prepared.make_debugger(stdin="A")
    assert debug.snapshot() == debug.vm.snapshot() == (0,)
    assert vm.run_until_halt_or_cycle(debug, limit=1) is False
    evaluation = artifact.evaluate([1], limits=active, catalog=termination.catalog)
    assert evaluation.termination.halts is False
    assert evaluation.termination.cycle.state == (0,)
    assert evaluation.observation == esolangs.ExecutionResult("1", 1, 1, 0, steps=1)

    class Intermediate:
        index = 0

        def step(self):
            self.index += 1

        @property
        def halted(self):
            return self.index == 3

        def snapshot(self):
            return ([2],) if self.index == 2 else (self.index,)

    machine = Intermediate()
    debug = prepared.make_debugger(stdin="A")
    with pytest.raises(TypeError, match="hashable state"):
        vm.run_until_halt_or_cycle(debug, limit=3)
    assert debug.observation == replace(expected, steps=2)
    machine = Intermediate()
    with pytest.raises(
        esolangs.InterpreterLimitError, match="hashable state"
    ) as caught:
        artifact.evaluate(
            [1],
            limits=esolangs.ExecutionLimits(max_steps=3),
            catalog=termination.catalog,
        )
    assert caught.value.observation == esolangs.ExecutionResult("1", 1, 1, 0, steps=2)

    # Matching the installed declaration does not certify replacement hooks.
    monkeypatch.setattr(interpreter, declaration.runtime.machine_preparation, prepare)
    machine = Intermediate()
    debug = api.make_debugger(source, stdin="A")
    with pytest.raises(TypeError, match="hashable state"):
        vm.run_until_halt_or_cycle(debug, limit=3)
    assert debug.observation == replace(expected, steps=2)

    _check_inherited_snapshot(
        monkeypatch, api, interpreter, declaration.runtime.machine_preparation
    )

    machine = SimpleNamespace(snapshot=lambda: 0)
    _check_invalid_halted(scoped, prepared, source, active, expected, machine)

    _check_reused_initialization_fault(scoped, interpreter, original, monkeypatch)


def _check_reused_initialization_fault(scoped, interpreter, original, monkeypatch):
    prior_observation = original.observation

    def reject(_source, _options):
        raise original

    monkeypatch.setattr(interpreter, "custom_initialize", reject)
    limits = esolangs.ExecutionLimits(max_steps=0)
    observed = scoped.run("+.", stdin="B", limits=limits)
    with pytest.raises(esolangs.ArgumentError, match="custom step binding") as reused:
        scoped.make_debugger("+.", stdin="B")
    assert reused.value is observed.error is original
    assert observed.observation == esolangs.ExecutionResult("", 0, 0, 0)
    assert original.observation is prior_observation
    assert original.partial_output == "A"


def _check_invalid_halted(scoped, prepared, source, limits, expected, machine):
    def refuse_step():
        pytest.fail("an invalid halted value cannot decide whether to step")

    machine.step = refuse_step
    diagnostic = "machine halted must be a bool"
    declaration = scoped.catalog.languages[scoped.name]
    runtime = replace(
        declaration.runtime,
        capabilities=replace(
            declaration.runtime.capabilities, completion=Completion.POST_HALT
        ),
    )
    dumping = Catalog([replace(declaration, runtime=runtime)]).bind(scoped.name)

    for invalid in ("still active", 0, refuse_step):
        machine.halted = invalid
        direct = scoped.make_vm(source, stdin="A")
        debug = prepared.make_debugger(stdin="A")
        assert direct.output == debug.output == "A"
        for inspect, receiver, steps in (
            (lambda vm: vm.halted, direct, None),
            (lambda vm: vm.halted, debug, 0),
            (lambda debugger: debugger.run(limits=limits), debug, 0),
            (lambda vm_: vm.run_until_halt_or_cycle(vm_, limit=1), direct, None),
            (lambda vm_: vm.run_until_halt_or_cycle(vm_, limit=1), debug, 0),
            (lambda vm_: vm.complete_vm(vm_, max_steps=1), direct, 0),
        ):
            with pytest.raises(
                esolangs.InterpreterLimitError, match=diagnostic
            ) as caught:
                inspect(receiver)
            assert caught.value.observation == replace(expected, steps=steps)
            assert caught.value.partial_output == "A"

        for outcome in (
            scoped.run(source, stdin="A", limits=limits),
            prepared.run(stdin="A", limits=limits),
        ):
            assert outcome.status == "limit"
            assert isinstance(outcome.error, esolangs.InterpreterLimitError)
            assert diagnostic in str(outcome.error)
            assert (
                outcome.observation
                == outcome.error.observation
                == replace(expected, steps=0)
            )
            assert outcome.error.partial_output == "A"

        with pytest.raises(esolangs.InterpreterLimitError, match=diagnostic) as caught:
            dumping.make_vm(source, stdin="A").step()
        assert caught.value.observation == expected


def _check_inherited_snapshot(monkeypatch, api, interpreter, hook):
    class ExternalMachine(_Machine):
        @property
        def state(self):
            index, pointer, tape = self._state
            return (index, pointer, list(tape)) if index == 2 else self._state

        @state.setter
        def state(self, value):
            index, pointer, tape = value
            self._state = (index, pointer, tuple(tape))

    def subclassed(source, _options):
        def initialize(io):
            return ExternalMachine(source, io)

        return initialize

    monkeypatch.setattr(interpreter, hook, subclassed)
    debug = api.make_debugger(">>><")
    with pytest.raises(TypeError, match="hashable state"):
        vm.run_until_halt_or_cycle(debug, limit=4)
    assert debug.observation.steps == 2


@pytest.mark.parametrize("phase", ["native", "initialize", "step"])
@pytest.mark.parametrize("completed", [False, True])
def test_runtime_hooks_keep_nested_errors_and_record_their_own_output(
    monkeypatch, phase, completed
) -> None:
    from esolangs.runtime._execution import interpreter_module

    api = esolangs.Language(REFERENCE)
    declaration = api.catalog.languages[api.name]
    interpreter = interpreter_module(api.name)
    failures = []

    def invoke_nested(io):
        io.print_str("outer:" + chr(io.input_char()))
        try:
            if completed:
                api.from_source(",+.").evaluate([1], catalog=api.catalog)
            else:
                api.run(
                    ",.,", stdin="A", limits=esolangs.ExecutionLimits(max_steps=3)
                ).unwrap()
        except esolangs.EsolangError as error:
            failures.append(error)
            raise

    def native(_source, io):
        invoke_nested(io)

    def prepare(_source, _options):
        def machine(io):
            if phase == "initialize":
                invoke_nested(io)
            return SimpleNamespace(
                halted=False, step=lambda: invoke_nested(io), snapshot=lambda: 0
            )

        return machine

    monkeypatch.setattr(interpreter, "nested_native", native, raising=False)
    monkeypatch.setattr(interpreter, "nested_prepare", prepare, raising=False)
    runtime = replace(
        declaration.runtime,
        completion_entrypoint="nested_native",
        machine_preparation="nested_prepare",
    )
    scoped = Catalog([replace(declaration, runtime=runtime)]).bind(api.name)
    limits = None if phase == "native" else esolangs.ExecutionLimits(max_steps=4)
    result = scoped.run("+.", stdin="B", limits=limits)
    assert result.status == ("rejected" if completed else "input_exhausted")
    assert failures == [result.error]
    assert result.observation == esolangs.ExecutionResult(
        "outer:B", 1, 1, 0, steps=0 if phase == "step" else None
    )
    expected = (
        api.run(",+.", stdin="1").unwrap()
        if completed
        else esolangs.ExecutionResult("A", 1, 1, 1, steps=2)
    )
    error_type = esolangs.ProgramError if completed else esolangs.InputExhaustedError

    def check_original(error):
        assert error is failures[-1]
        assert error.partial_output == expected.output
        assert error.observation == expected

    with pytest.raises(error_type) as caught:
        result.unwrap()
    check_original(caught.value)
    if phase == "step":
        debugger = scoped.make_debugger("+.", stdin="B")
        with pytest.raises(error_type) as caught:
            debugger.step()
        check_original(caught.value)
        assert debugger.observation == result.observation

        from esolangs.debugger import Debugger

        for machine in (
            scoped.make_vm("+.", stdin="B"),
            scoped.make_debugger("+.", stdin="B"),
            Debugger(Debugger(scoped.make_debugger("+.", stdin="B"))),
        ):
            with pytest.raises(error_type) as caught:
                vm.complete_vm(machine)
            check_original(caught.value)
            assert machine.output == result.observation.output

        contract = replace(
            declaration.contract,
            answer_mode="termination",
            answer_values=("halts", "diverges"),
        )
        termination = Catalog(
            [replace(declaration, runtime=runtime, contract=contract)]
        ).bind(api.name)
        with pytest.raises(error_type) as caught:
            termination.from_source("+.").evaluate(
                [0], limits=limits, catalog=termination.catalog
            )
        check_original(caught.value)


def test_worker_runtime_guard_uses_the_shipped_catalog(monkeypatch) -> None:
    from esolangs.registry import _table
    from esolangs.runtime import _isolated

    api = esolangs.Language(REFERENCE)
    declaration = api.catalog.languages[api.name]
    scoped = Catalog([declaration]).bind(api.name)
    assert (
        scoped.run(",.", stdin="A", isolated=True).unwrap()
        == scoped.run(",.", stdin="A").unwrap()
    )

    changed = replace(declaration.runtime, completion_entrypoint="alternate_hook")
    custom = Catalog([replace(declaration, runtime=changed)])

    def launch(*_args, **_kwargs):
        pytest.fail("a changed runtime reached the worker")

    def refuses(binding):
        source, stdin = StringIO(",."), StringIO("A")
        outcome = binding.run(source, stdin=stdin, isolated=True)
        assert isinstance(outcome.error, esolangs.ArgumentError)
        assert "runtime declared in the installed catalog" in str(outcome.error)
        assert source.tell() == stdin.tell() == 0

    monkeypatch.setattr(_isolated, "_launch", launch)
    refuses(custom.bind(api.name))
    monkeypatch.setattr(_table, "CATALOG", custom)
    refuses(esolangs.Language(api.name))


def test_worker_rejects_scoped_runtime_before_dialect_hook() -> None:
    api = esolangs.Language(REFERENCE)
    declaration = api.catalog.languages[api.name]
    calls = []
    allow_hook = True

    class Validator:
        __hash__ = object.__hash__

        def __eq__(self, other):
            pytest.fail("worker preflight compared a caller's dialect hook")

        def __call__(self, *, mode="default"):
            if not allow_hook:
                pytest.fail("worker preflight called an unsupported dialect hook")
            calls.append(mode)

    schema = esolangs.DialectSchema(
        api.name, {"mode": ("default",)}, {"mode": "default"}
    )
    runtime = replace(declaration.runtime, dialect=Validator(), dialect_schema=schema)
    scope = Catalog([replace(declaration, runtime=runtime)]).bind(api.name)
    # An empty override uses the scoped hook's default without adding a runner keyword.
    settings = scope.settings()
    prepared = scope.prepare(",.", settings=settings)
    calls.clear()
    assert scope.run(",.", stdin="A", settings=settings).unwrap().output == "A"
    assert calls
    assert all(mode == "default" for mode in calls)
    assert prepared.run(stdin="A").unwrap().output == "A"

    allow_hook = False
    for options in (
        {"isolated": True},
        {"limits": esolangs.ExecutionLimits(total_timeout=5)},
    ):
        source, stdin = StringIO(",."), StringIO("A")
        for outcome in (
            scope.run(source, stdin=stdin, settings=settings, **options),
            prepared.run(stdin=stdin, **options),
        ):
            assert isinstance(outcome.error, esolangs.ArgumentError)
            assert "runtime declared in the installed catalog" in str(outcome.error)
        assert source.tell() == stdin.tell() == 0


def test_worker_rejects_unmatched_hook_name_without_custom_equality() -> None:
    api = esolangs.Language(REFERENCE)
    declaration = api.catalog.languages[api.name]

    class OtherHook(str):
        __hash__ = str.__hash__

        def __eq__(self, other):
            pytest.fail("worker preflight compared a caller's hook name")

    changed = replace(
        declaration.runtime, completion_entrypoint=OtherHook("extra_hook")
    )
    scope = Catalog([replace(declaration, runtime=changed)]).bind(api.name)
    outcome = scope.run(",.", stdin="A", isolated=True)
    assert isinstance(outcome.error, esolangs.ArgumentError)
    assert "runtime declared in the installed catalog" in str(outcome.error)
