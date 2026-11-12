"""Declared raster factories retain cached geometry and isolated run state."""

import pytest

import esolangs
from esolangs.debugger import make_debugger
from esolangs.languages.line import interpreter
from esolangs.languages.line.generator import line
from esolangs.raster import Raster
from esolangs.runtime.io import ScriptedIO


def test_factory_keeps_cached_geometry_and_fresh_tape_and_input(monkeypatch):
    source = Raster.from_png(line("01").to_png())
    interpreter._compiled.cache_clear()
    factory = interpreter.prepare_machine(source, {})
    first, second = factory(ScriptedIO("0")), factory(ScriptedIO("1"))
    assert interpreter._compiled.cache_info().misses == 1
    assert interpreter._compiled.cache_info().hits == 0
    assert first.program is second.program
    before = second.snapshot()
    while not first.halted:
        first.step()
    assert first.io.getvalue() == "0"
    assert second.snapshot() == before
    assert second.io.position() == 0
    assert second.memory == (0,)
    third = factory(ScriptedIO("1"))
    assert third.snapshot() == before
    while not second.halted:
        second.step()
    assert second.io.getvalue() == "1"
    assert third.snapshot() == before
    native_io = ScriptedIO("1")
    factory.run(native_io)
    assert native_io.getvalue() == "1"
    assert interpreter._compiled.cache_info().hits == 0

    generated = line("01")
    with monkeypatch.context() as patch:

        def unexpected_compile(*_args, **_kwargs):
            pytest.fail("generated native execution extracted raster geometry")

        freeze_node = interpreter._freeze_node
        frozen = []

        def counted(node):
            frames = freeze_node(node)
            frozen.append(frames)
            return frames

        patch.setattr(interpreter, "_compiled", unexpected_compile)
        patch.setattr(interpreter, "_freeze_node", counted)
        prepared = esolangs.Language("Line").prepare(generated)
        assert frozen == []
        assert prepared.run(stdin="1").output == "1"
        assert prepared.run(stdin="0").output == "0"
        assert len(frozen) == 1


@pytest.mark.medium
def test_scale_binding_preserves_graph_and_raster_execution_paths():
    for scale in (1, 2, 3):
        generated = line("01", scale=scale)
        for source in (generated, Raster.from_png(generated.to_png())):
            native = esolangs.run("Line", source, stdin="1")
            assert native.output == "1"
            options = {"scale": scale}
            factory = interpreter.prepare_machine(source, options)
            options["scale"] = 0
            machine = factory(ScriptedIO("1"))
            while not machine.halted:
                machine.step()
            assert machine.io.getvalue() == native.output
            debug = make_debugger("Line", source, stdin="1", scale=scale)
            assert debug.run(max_steps=1000) == "halted"
            result, snapshot = debug.observation, debug.snapshot()
            assert result == native._replace(steps=result.steps)
            assert esolangs.run("Line", source, stdin="1", scale=scale) == native
            assert (
                esolangs.run("Line", source, stdin="1", scale=scale, isolated=True)
                == native
            )
            debug.step()
            assert debug.run(max_steps=0) == "halted"
            assert (debug.observation, debug.snapshot()) == (result, snapshot)


def test_factory_rejects_unprepared_source_and_options():
    with pytest.raises(TypeError, match="raster source"):
        interpreter.prepare_machine("", {})
    with pytest.raises(TypeError, match="only the scale"):
        interpreter.prepare_machine(line("01"), {"unexpected": True})
