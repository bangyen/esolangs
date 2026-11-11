"""Prepared readings share immutable statements and keep variables per run."""

import pytest

from esolangs.languages.qoibl import interpreter
from esolangs.runtime.io import ScriptedIO


def test_factory_reuses_reading_with_private_variables(monkeypatch):
    interpreter._tokenized.cache_clear()
    source = ["we y we et we", "tt qe y qe tt"]
    factory = interpreter.prepare_machine(source, {})
    source.clear()
    first, second = factory(ScriptedIO("A")), factory(ScriptedIO("B"))
    assert interpreter._tokenized.cache_info().misses == 1
    assert interpreter._tokenized.cache_info().hits == 0
    assert first.code is second.code
    before = second.snapshot()
    first.step()
    assert first.memory[1] == 65
    first.step()
    assert first.io.getvalue() == "A"
    assert second.snapshot() == before
    assert second.memory[1] == 0
    assert second.io.position() == 0
    interpreter._tokenized.cache_clear()
    third = factory(ScriptedIO("C"))
    assert third.code is second.code
    assert interpreter._tokenized.cache_info().misses == 0
    assert third.snapshot() == before
    while not second.halted:
        second.step()
    assert second.io.getvalue() == "B"
    assert third.snapshot() == before

    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Qoibl",
        "we y we et we\ntt qe y qe tt",
        interpreter,
        "_prepare_source",
        monkeypatch,
    )


def test_factory_preserves_text_and_split_statement_boundaries():
    source = "tt y tt\ntt ye tt"
    for value in (source, source.splitlines()):
        machine = interpreter.prepare_machine(value, {})(ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == "\x01\x02"


def test_factory_rejects_unprepared_source_and_options():
    with pytest.raises(TypeError, match="text or split text"):
        interpreter.prepare_machine(None, {})
    with pytest.raises(TypeError, match="no runtime options"):
        interpreter.prepare_machine([], {"unexpected": True})
