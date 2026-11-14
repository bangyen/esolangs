"""Compressed preparation retains Unary decoding and EOF semantics."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

import esolangs
from esolangs import vm
from esolangs.compressed import CompressedText
from esolangs.debugger import make_debugger
from esolangs.languages.unary import interpreter
from esolangs.runtime.io import ScriptedIO


def test_compressed_factory_keeps_source_and_owns_fresh_state(monkeypatch):
    source = CompressedText.from_chunks(("0" * 684,))  # +,.

    def expanded(_self):
        raise AssertionError("compressed source expanded")

    monkeypatch.setattr(CompressedText, "__str__", expanded)
    factory = interpreter.prepare_machine(source, {})
    first, second = factory(ScriptedIO()), factory(ScriptedIO("A"))
    assert type(first) is type(second) is interpreter._Machine
    first.step()
    assert first.memory == [1]
    assert second.memory == [0]
    first.step()
    first.step()
    assert first.halted
    assert first.io.getvalue() == "\0"
    assert (first.io.reads, first.io.past_end) == (0, 1)
    assert second.snapshot() == interpreter._Machine(source, ScriptedIO("A")).snapshot()
    monkeypatch.setattr(
        vm,
        "interpreter_module",
        lambda _name, **_options: SimpleNamespace(
            prepare_machine=interpreter.prepare_machine
        ),
    )
    for value in (source, source.to_gzip()):
        native = esolangs.run("Unary", value)
        assert native.output == "\0"
        assert (native.input_position, native.input_reads, native.input_past_end) == (
            0,
            0,
            1,
        )
        debug = make_debugger("Unary", value)
        assert debug.views == ()
        assert debug.eof_is_a_value
        assert debug.ip_shape == "offset"
        assert debug.run(limits=esolangs.ExecutionLimits(max_steps=3)) == "halted"
        assert debug.observation == replace(native, steps=3)
        before = debug.observation, debug.snapshot()
        debug.step()
        assert debug.run(limits=esolangs.ExecutionLimits(max_steps=0)) == "halted"
        assert (debug.observation, debug.snapshot()) == before
        assert esolangs.run("Unary", value, isolated=True) == native


def test_factory_rejects_unprepared_sources_and_options():
    with pytest.raises(TypeError, match="text or compressed"):
        interpreter.prepare_machine([], {})
    with pytest.raises(TypeError, match="no runtime options"):
        interpreter.prepare_machine("0", {"unexpected": True})
