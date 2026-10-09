"""Deadfish through the shared API, CLI and machinery."""

import pytest

import esolangs
from esolangs._evaluate import _evaluate


def test_generate_refuses_a_language_with_no_generator() -> None:
    """A registered language may have no generator, and must say so."""
    with pytest.raises(esolangs.ArgumentError) as exc:
        esolangs.generate("Deadfish", "0110")
    message = str(exc.value)
    assert "no boolean generator" in message
    assert "generator contracts" in message
    assert "'int'" in message


def test_supplied_program_never_generates(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("evaluation called a generator")

    monkeypatch.setattr(esolangs, "generate", refuse)
    assert _evaluate("brainfuck", ",>,<.", inputs=2) == "0011"
    assert _evaluate("Deadfish", "o", inputs=1) == "00"
