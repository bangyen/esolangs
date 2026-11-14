"""Declared construction owns fresh state and preserves source-step behavior."""

from dataclasses import replace
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


def test_preparation_requires_a_callable_factory(monkeypatch) -> None:
    from esolangs.runtime._execution import interpreter_module

    api = esolangs.Language(REFERENCE)
    runtime = api.catalog.languages[api.name].runtime
    interpreter = interpreter_module(api.name)
    monkeypatch.setattr(interpreter, runtime.machine_preparation, lambda *_args: None)
    for operation in (api.prepare, api.make_vm):
        with pytest.raises(esolangs.InterpreterLimitError, match="no machine factory"):
            operation("+.")
