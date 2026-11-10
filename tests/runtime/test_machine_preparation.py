"""Declared construction owns fresh state and preserves source-step behavior."""

from types import SimpleNamespace

import pytest

from esolangs import vm
from esolangs.languages.brainfuck.interpreter import _Machine, prepare_machine
from esolangs.results import Completion


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
