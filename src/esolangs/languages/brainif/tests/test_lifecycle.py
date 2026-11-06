"""Prepared source and tape/input state stay private across BrainIf runs."""

import pytest

from esolangs.languages.brainif import interpreter
from esolangs.runtime.io import ScriptedIO


def test_factory_binds_source_with_private_code_and_tape():
    source = ["if 0 input", "if 65 output", "if 0 left", "if 0 increment"]
    factory = interpreter.prepare_machine(source, {})
    first, second = factory(ScriptedIO("A")), factory(ScriptedIO("B"))
    source.clear()
    assert first.code == second.code
    assert first.code is not second.code
    before = second.snapshot()
    first.step()
    assert first.memory == [65]
    assert second.snapshot() == before
    assert second.io.position() == 0
    while not first.halted:
        first.step()
    assert first.io.getvalue() == "A"
    first.code.clear()
    third = factory(ScriptedIO("C"))
    assert third.code == second.code
    assert third.snapshot() == before
    while not second.halted:
        second.step()
    assert second.memory == [66]
    assert second.io.getvalue() == ""
    assert third.snapshot() == before

    with pytest.raises(TypeError, match="split text"):
        interpreter.prepare_machine("if 0 input", {})
    with pytest.raises(TypeError, match="no runtime options"):
        interpreter.prepare_machine([], {"unexpected": True})
