"""Prepared source and tape/input state stay private across BrainIf runs."""

from esolangs.languages.brainif import interpreter
from esolangs.runtime.io import ScriptedIO
from tests.support.prepared_support import check_split_factory_rejections


def test_factory_shares_source_with_private_tape(monkeypatch):
    source = ["if 0 input", "if 65 output", "if 0 left", "if 0 increment"]
    parse = interpreter._parse
    parsed = []

    def record(line):
        parsed.append(line)
        return parse(line)

    monkeypatch.setattr(interpreter, "_parse", record)
    factory = interpreter.prepare_machine(source, {})
    first, second = factory(ScriptedIO("A")), factory(ScriptedIO("B"))
    source.clear()
    assert first.code is second.code
    assert parsed == []
    before = second.snapshot()
    first.step()
    assert first.memory == [65]
    assert second.snapshot() == before
    assert second.io.position() == 0
    while not first.halted:
        first.step()
    assert first.io.getvalue() == "A"
    first.code = ()
    third = factory(ScriptedIO("C"))
    assert third.code == second.code
    assert third.snapshot() == before
    while not second.halted:
        second.step()
    assert second.memory == [66]
    assert second.io.getvalue() == ""
    assert third.snapshot() == before
    native_io = ScriptedIO("A")
    factory.run(native_io)
    assert native_io.getvalue() == "A"
    assert parsed == list(second.code)
    check_split_factory_rejections(interpreter.prepare_machine, ["if 0 input"])
