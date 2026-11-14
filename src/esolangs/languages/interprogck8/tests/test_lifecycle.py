"""Prepared programs retain private call/reload state and explicit RNG draws."""

from dataclasses import replace

import pytest

import esolangs
from esolangs.debugger import make_debugger
from esolangs.languages.interprogck8 import interpreter
from esolangs.runtime.io import ScriptedIO


def test_factory_reuses_compilation_with_private_call_state():
    interpreter._from_json.cache_clear()
    source = "nNnN\n<\n@nd\n>\nEXE\ndiv"
    factory = interpreter.prepare_machine(source, {})
    first, second = factory(ScriptedIO()), factory(ScriptedIO())
    assert interpreter._from_json.cache_info().misses == 1
    assert interpreter._from_json.cache_info().hits == 0
    assert first._program is second._program
    before = second.snapshot()
    for _ in range(3):
        first.step()
    assert first.stack == [0]
    assert second.snapshot() == before
    while not first.halted:
        first.step()
    assert first.io.getvalue() == "B"
    assert second.memory == [0]
    assert second.stack == []
    interpreter._from_json.cache_clear()
    third = factory(ScriptedIO())
    assert third._program is second._program
    assert third.snapshot() == before
    assert interpreter._from_json.cache_info().misses == 0


def test_split_factory_binds_source_and_reloads_only_its_own_program():
    source = "nNnN\ndiv\nEmpty_\nz\n@id\ndiv".splitlines()
    factory = interpreter.prepare_machine(source, {})
    first, second = factory(ScriptedIO()), factory(ScriptedIO())
    source.clear()
    before = second.snapshot()
    while not first.halted:
        first.step()
    assert first.io.getvalue() == "AAK"
    assert len(first.state.lines) == 4
    assert second.snapshot() == before
    assert factory(ScriptedIO()).snapshot() == before


def test_rng_binding_draws_only_during_execution():
    class Recording:
        def __init__(self):
            self.calls = []

        def randbelow(self, upper):
            self.calls.append(upper)
            return upper - 1

    rng = Recording()
    options = {"rng": rng}
    factory = interpreter.prepare_machine("~\n[. :::]\n$ay", options)
    options.clear()
    first, second = factory(ScriptedIO()), factory(ScriptedIO())
    assert first.rng is second.rng is rng
    assert rng.calls == []
    before = second.snapshot()
    while not first.halted:
        first.step()
    assert rng.calls == [10, 6]
    assert first.io.getvalue() == ":::"
    assert second.snapshot() == before
    for seed in range(4):
        source = "~\n[. :::]\n$ay"
        native = esolangs.run("Interprogck8", source, seed=seed)
        debug = make_debugger("Interprogck8", source, seed=seed)
        assert debug.run(limits=esolangs.ExecutionLimits(max_steps=3)) == "halted"
        assert debug.observation == replace(native, steps=3)
        assert esolangs.run("Interprogck8", source, seed=seed, isolated=True) == native


def test_factory_rejects_unprepared_source_and_options():
    with pytest.raises(TypeError, match="text or split text"):
        interpreter.prepare_machine(esolangs.CompressedText.from_chunks(("",)), {})
    with pytest.raises(TypeError, match="only the rng"):
        interpreter.prepare_machine([], {"unexpected": True})
