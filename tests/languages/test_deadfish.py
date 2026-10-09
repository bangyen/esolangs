"""Deadfish through the shared API, CLI and machinery."""

import pytest

import esolangs


def test_generate_refuses_a_language_with_no_generator() -> None:
    """A registered language may have no generator, and must say so."""
    with pytest.raises(esolangs.ArgumentError) as exc:
        esolangs.generate("Deadfish", "0110")
    message = str(exc.value)
    assert "no boolean generator" in message
    assert "generator contracts" in message
    assert "'int'" in message
