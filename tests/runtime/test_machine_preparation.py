"""Declared construction owns fresh state and preserves source-step behavior."""

from types import SimpleNamespace

import pytest

from esolangs import vm
from esolangs.languages.brainfuck.interpreter import prepare_machine
from esolangs.runtime.io import ScriptedIO


def test_declared_preparation_needs_no_private_constructor(monkeypatch):
    calls = []

    def prepare(source, options):
        calls.append((source, dict(options)))
        return prepare_machine(source, options)

    monkeypatch.setattr(
        vm, "interpreter_module", lambda _name: SimpleNamespace(prepare_machine=prepare)
    )
    machine = vm.make_vm("brainfuck", ",+.", stdin="A")
    assert calls == [(",+.", {})]
    assert machine.ip == 0
    machine.step()
    assert machine.ip == 1
    machine.step()
    machine.step()
    assert machine.halted
    assert machine.output == "B"


def test_prepared_factory_owns_state_and_input():
    factory = prepare_machine(",+.", {})
    first_io, second_io = ScriptedIO("A"), ScriptedIO("Z")
    first, second = factory(first_io), factory(second_io)
    before = second.snapshot()
    first.step()
    assert second.snapshot() == before
    assert second_io.progress() == 0
    while not first.halted:
        first.step()
    while not second.halted:
        second.step()
    assert first_io.getvalue() == "B"
    assert second_io.getvalue() == "["


def test_preparation_refuses_wrong_shapes_and_options():
    with pytest.raises(TypeError, match="text source"):
        prepare_machine(["+"], {})
    with pytest.raises(TypeError, match="no runtime options"):
        prepare_machine("+", {"rng": object()})
