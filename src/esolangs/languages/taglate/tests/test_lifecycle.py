"""Prepared commands share immutable tokens and keep queue state per run."""

import pytest

from esolangs.languages.taglate import interpreter
from esolangs.runtime.io import ScriptedIO


def test_factory_keeps_cached_tokens_and_fresh_run_state(monkeypatch):
    interpreter._program.cache_clear()
    calls = []
    tokenize = interpreter._tokens

    def counted(commands):
        calls.append(commands)
        return tokenize(commands)

    monkeypatch.setattr(interpreter, "_tokens", counted)
    source = ["AB", "efgyfgz"]
    factory = interpreter.prepare_machine(source, {})
    source[0] = "changed"
    first, second = factory(ScriptedIO()), factory(ScriptedIO())
    assert calls == ["efgyfgz"]
    assert first.tokens == second.tokens == ("e", "f", "gy", "f", "gz")
    assert first.match == second.match == {2: 4, 4: 2}
    assert first.tokens is second.tokens
    assert first.match is second.match
    before = second.snapshot()
    first.step()
    first.step()
    assert first.queue == (65,)
    assert second.snapshot() == before
    interpreter._program.cache_clear()
    third = factory(ScriptedIO())
    assert third.snapshot() == before
    assert third.tokens is second.tokens
    assert third.match is second.match
    assert calls == ["efgyfgz"]

    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Taglate",
        "AB\nefhii",
        interpreter,
        "_prepare_source",
        monkeypatch,
        cases=(("A", "AA"), ("B", "AB"), ("C", "AC")),
    )


def test_factory_rejects_unprepared_source_and_options():
    with pytest.raises(TypeError, match="split text"):
        interpreter.prepare_machine("A\ni", {})
    with pytest.raises(TypeError, match="no runtime options"):
        interpreter.prepare_machine(["A", "i"], {"unexpected": True})
