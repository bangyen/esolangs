"""Cached memory images stay immutable across self-modifying runs."""

import pytest

from esolangs.languages.malbolge import interpreter
from esolangs.runtime.io import ScriptedIO


def test_factory_reuses_image_with_private_memory_and_chunks():
    interpreter._initial_memory.cache_clear()
    factory = interpreter.prepare_machine("ubO", {})
    first, second = factory(ScriptedIO()), factory(ScriptedIO("A"))
    assert interpreter._initial_memory.cache_info().misses == 1
    assert interpreter._initial_memory.cache_info().hits == 1
    assert first.memory is not second.memory
    assert first._chunks is not second._chunks
    assert first._dirty is not second._dirty
    before = second.snapshot()
    first.step()
    assert first.state[0] == 59048
    assert first.memory[0] != ord("u")
    assert first._dirty
    first.snapshot()
    assert not first._dirty
    assert second.snapshot() == before
    third = factory(ScriptedIO("Z"))
    assert third.snapshot() == before
    assert third.memory[0] == ord("u")
    for machine in (first, second):
        while not machine.halted:
            machine.step()
    assert first.io.getvalue() == "¨"
    assert first.io.past_end == 1
    assert second.io.getvalue() == "A"
    assert second.io.reads == 1
    assert third.snapshot() == before
    assert interpreter._initial_memory("ubO")[0] == ord("u")


def test_factory_rejects_unprepared_source_and_options():
    with pytest.raises(TypeError, match="text source"):
        interpreter.prepare_machine([], {})
    with pytest.raises(TypeError, match="no runtime options"):
        interpreter.prepare_machine("Q", {"unexpected": True})
