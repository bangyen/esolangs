"""Declared construction owns fresh state and preserves source-step behavior."""

from dataclasses import replace
from io import StringIO
from types import SimpleNamespace

import pytest

import esolangs
from esolangs import vm
from esolangs.languages.brainfuck.interpreter import _Machine, prepare_machine
from esolangs.results import Completion
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
    wrapped = esolangs.Catalog([replace(record, runtime=runtime)]).bind(api.name)
    assert wrapped.run("+.").output == "\x01"
    debugger = wrapped.make_debugger("+.")
    assert debugger.run(limits=esolangs.ExecutionLimits(max_steps=2)) == "halted"
    assert debugger.output == "\x01"

    no_prepare = replace(record.runtime, machine_preparation="absent_preparation")
    scoped = esolangs.Catalog([replace(record, runtime=no_prepare)]).bind(api.name)
    assert scoped.run("+.").output == "\x01"
    for operation in (scoped.prepare, scoped.make_vm, scoped.make_debugger):
        with pytest.raises(esolangs.ProgramError, match="absent_preparation"):
            operation("+.")
    no_completion = replace(record.runtime, completion_entrypoint="absent_completion")
    scoped = esolangs.Catalog([replace(record, runtime=no_completion)]).bind(api.name)
    assert isinstance(scoped.execute("+.").error, esolangs.ProgramError)
    with pytest.raises(esolangs.ProgramError, match="absent_completion"):
        scoped.run("+.")
    assert (
        scoped.run("+.", limits=esolangs.ExecutionLimits(max_steps=2)).output == "\x01"
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
            prepared.run(stdin=stdin, limits=limits)
        assert stdin.bindings == 1
        assert stdin.tell() == 0
        with pytest.raises(esolangs.ArgumentError, match="stdin must"):
            prepared.run(stdin=object(), limits=limits)
    assert prepared.run(limits=esolangs.ExecutionLimits(max_steps=2)).output == "\x01"


@pytest.mark.parametrize("hook", ["completion_entrypoint", "machine_preparation"])
def test_native_prepared_runs_apply_the_declared_hooks(monkeypatch, hook) -> None:
    from esolangs.registry import _table
    from esolangs.runtime._execution import interpreter_module
    from esolangs.runtime._lifecycle import HALTED_REPORT
    from esolangs.runtime._machine import RuntimePlan
    from esolangs.runtime._prepared import _installed_plan_hooks

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
    catalog = esolangs.Catalog([replace(declaration, runtime=runtime)])
    scoped = catalog.bind(api.name)
    artifact = scoped.from_source(",.")
    prepared = scoped.prepare(artifact)
    result = prepared.run(stdin="A")
    assert result == scoped.run(artifact, stdin="A")
    assert result.output == ("custom: A" if native else "A")
    assert prepared.evaluate([1]) == scoped.evaluate(artifact, [1])
    assert (
        prepared.run(stdin="A", limits=esolangs.ExecutionLimits(max_steps=2)).output
        == "A"
    )
    monkeypatch.setattr(_table, "CATALOG", catalog)
    _installed_plan_hooks.cache_clear()
    try:
        assert esolangs.prepare(api.name, artifact).run(stdin="A") == result
    finally:
        _installed_plan_hooks.cache_clear()


def test_preparation_requires_a_callable_factory(monkeypatch) -> None:
    from esolangs.runtime._execution import interpreter_module

    api = esolangs.Language(REFERENCE)
    runtime = api.catalog.languages[api.name].runtime
    interpreter = interpreter_module(api.name)
    monkeypatch.setattr(interpreter, runtime.machine_preparation, lambda *_args: None)
    for operation in (api.prepare, api.make_vm):
        with pytest.raises(esolangs.InterpreterLimitError, match="no machine factory"):
            operation("+.")


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
                api.evaluate(api.from_source(",+."), [1])
            else:
                api.run(",.,", stdin="A", limits=esolangs.ExecutionLimits(max_steps=3))
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
    scoped = esolangs.Catalog([replace(declaration, runtime=runtime)]).bind(api.name)
    limits = None if phase == "native" else esolangs.ExecutionLimits(max_steps=4)
    result = scoped.execute("+.", stdin="B", limits=limits)
    assert result.status == ("rejected" if completed else "input_exhausted")
    assert failures == [result.error]
    assert result.observation == esolangs.ExecutionResult(
        "outer:B", 1, 1, 0, steps=0 if phase == "step" else None
    )
    expected = (
        api.run(",+.", stdin="1")
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

        machine = scoped.make_vm("+.", stdin="B")
        with pytest.raises(error_type) as caught:
            vm.complete_vm(machine)
        check_original(caught.value)
        assert machine.output == result.observation.output

        contract = replace(
            declaration.contract,
            answer_mode="termination",
            answer_values=("halts", "diverges"),
        )
        termination = esolangs.Catalog(
            [replace(declaration, runtime=runtime, contract=contract)]
        ).bind(api.name)
        with pytest.raises(error_type) as caught:
            termination.evaluate(termination.from_source("+."), [0], limits=limits)
        check_original(caught.value)


def test_worker_runtime_guard_uses_the_shipped_catalog(monkeypatch) -> None:
    from esolangs.registry import _table
    from esolangs.runtime import _isolated

    api = esolangs.Language(REFERENCE)
    declaration = api.catalog.languages[api.name]
    scoped = esolangs.Catalog([declaration]).bind(api.name)
    assert scoped.run(",.", stdin="A", isolated=True) == scoped.run(",.", stdin="A")

    changed = replace(declaration.runtime, completion_entrypoint="alternate_hook")
    custom = esolangs.Catalog([replace(declaration, runtime=changed)])

    def launch(*_args, **_kwargs):
        pytest.fail("a changed runtime reached the worker")

    def refuses(binding):
        source, stdin = StringIO(",."), StringIO("A")
        outcome = binding.execute(source, stdin=stdin, isolated=True)
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
    scope = esolangs.Catalog([replace(declaration, runtime=runtime)]).bind(api.name)
    # An empty override uses the scoped hook's default without adding a runner keyword.
    settings = scope.settings()
    prepared = scope.prepare(",.", settings=settings)
    calls.clear()
    assert scope.run(",.", stdin="A", settings=settings).output == "A"
    assert calls
    assert all(mode == "default" for mode in calls)
    assert prepared.run(stdin="A").output == "A"

    allow_hook = False
    for options in (
        {"isolated": True},
        {"limits": esolangs.ExecutionLimits(total_timeout=5)},
    ):
        source, stdin = StringIO(",."), StringIO("A")
        for outcome in (
            scope.execute(source, stdin=stdin, settings=settings, **options),
            prepared.execute(stdin=stdin, **options),
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
    scope = esolangs.Catalog([replace(declaration, runtime=changed)]).bind(api.name)
    outcome = scope.execute(",.", stdin="A", isolated=True)
    assert isinstance(outcome.error, esolangs.ArgumentError)
    assert "runtime declared in the installed catalog" in str(outcome.error)
