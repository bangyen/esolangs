"""Cached geometry is shared; tape, input and car state belong to each run."""

import pytest

from esolangs.languages.streetcode import interpreter
from esolangs.runtime.io import ScriptedIO


def test_factory_reuses_geometry_with_fresh_run_state(monkeypatch):
    interpreter._Machine._compile.cache_clear()
    calls = []
    validate = interpreter._Machine._validate

    def counted(machine, start):
        calls.append(start)
        validate(machine, start)

    monkeypatch.setattr(interpreter._Machine, "_validate", counted)
    source = ["CI^O;"]
    factory = interpreter.prepare_machine(source, {})
    again = interpreter.prepare_machine(list(source), {})
    source[0] = "invalid"
    first, second = factory(ScriptedIO("A")), again(ScriptedIO("B"))
    assert len(calls) == 1
    assert first.grid is second.grid
    assert first._graph is second._graph
    before = second.snapshot()
    while not first.halted:
        first.step()
    assert first.io.getvalue() == "B"
    assert first.memory == [66]
    assert second.snapshot() == before
    assert second.io.position() == 0
    assert second.memory == []
    third = factory(ScriptedIO("Z"))
    assert third.snapshot() == before
    while not second.halted:
        second.step()
    assert second.io.getvalue() == "C"
    assert third.io.getvalue() == ""
    assert len(calls) == 1


def test_factory_rejects_unprepared_source_and_options():
    with pytest.raises(TypeError, match="split text"):
        interpreter.prepare_machine("C;", {})
    with pytest.raises(TypeError, match="no runtime options"):
        interpreter.prepare_machine(["C;"], {"unexpected": True})
