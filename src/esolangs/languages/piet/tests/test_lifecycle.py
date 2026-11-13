"""Prepared codel rows share no mutable stack, direction or input state."""

from dataclasses import replace

import pytest

import esolangs
from esolangs.debugger import make_debugger
from esolangs.languages.piet import interpreter
from esolangs.raster import Raster
from esolangs.runtime.codels import BLACK
from esolangs.runtime.io import ScriptedIO


def _echo() -> Raster:
    light_red, light_magenta, dark_blue = (255, 192, 192), (255, 192, 255), (0, 0, 192)
    return Raster(
        (
            (light_red, BLACK, BLACK, dark_blue),
            (light_red, light_red, light_magenta, dark_blue),
            (BLACK, BLACK, BLACK, dark_blue),
        )
    )


def test_factory_shares_rows_with_private_stack_and_read_count():
    factory = interpreter.prepare_machine(_echo(), {})
    first, second = factory(ScriptedIO("A")), factory(ScriptedIO("B"))
    assert first.rows is second.rows
    assert first._program_key is second._program_key
    before = second.snapshot()
    first.step()
    saved = first.workspace_snapshot()
    retained = {saved}
    first._program_key = ()
    first.snapshot = lambda: ("unrelated cycle key",)
    assert first.workspace_snapshot() == saved
    assert saved in retained
    assert first.stack == (65,)
    assert first._input_reads == 1
    assert second.snapshot() == before
    assert second.stack == ()
    assert second._input_reads == 0
    while not first.halted:
        first.step()
    assert first.io.getvalue() == "A"
    assert factory(ScriptedIO("C")).snapshot() == before
    while not second.halted:
        second.step()
    assert second.io.getvalue() == "B"
    native_io = ScriptedIO("D")
    factory.run(native_io)
    assert native_io.getvalue() == "D"


@pytest.mark.medium
def test_scale_binding_eof_and_unicode_match_all_routes():
    for stdin, scale in (("", 1), ("\0", 2), ("Ā", 3)):
        source = Raster.from_png(_echo().upscaled(scale).to_png())
        options = {"scale": scale}
        factory = interpreter.prepare_machine(source, options)
        options["scale"] = 0
        machine = factory(ScriptedIO(stdin))
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == stdin
        native = esolangs.run("Piet", source, stdin=stdin)
        assert native.output == stdin
        assert (native.input_position, native.input_reads, native.input_past_end) == (
            int(bool(stdin)),
            int(bool(stdin)),
            int(not stdin),
        )
        assert esolangs.run("Piet", source, stdin=stdin, scale=scale) == native
        debug = make_debugger("Piet", source, stdin=stdin, scale=scale)
        assert tuple(name for name, _ in debug.views) == ("cc", "current", "dp")
        assert debug.ip_shape == "grid"
        assert debug.eof_is_a_value
        assert debug.run(max_steps=20) == "halted"
        result, snapshot = debug.observation, debug.snapshot()
        assert result == replace(native, steps=result.steps)
        assert (
            esolangs.run("Piet", source, stdin=stdin, scale=scale, isolated=True)
            == native
        )
        debug.step()
        assert debug.run(max_steps=0) == "halted"
        assert (debug.observation, debug.snapshot()) == (result, snapshot)


def test_factory_rejects_unprepared_source_and_options():
    with pytest.raises(TypeError, match="raster source"):
        interpreter.prepare_machine("", {})
    with pytest.raises(TypeError, match="only the scale"):
        interpreter.prepare_machine(_echo(), {"unexpected": True})
