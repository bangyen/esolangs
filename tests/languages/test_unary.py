"""Unary through the shared API, CLI and machinery."""

import pytest

import esolangs


def test_unary_generator_refusal_does_not_deny_runtime_input() -> None:
    with pytest.raises(esolangs.ArgumentError, match="generator contracts") as caught:
        esolangs.generate("Unary", "01")
    assert "reads no input" not in str(caught.value)
