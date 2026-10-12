"""Befunge's fixed-torus refusal stays an explicit totality exception."""

import pytest

import esolangs
from tests.proofs._ledger import load


def test_befunge_refusal_is_an_explicit_totality_exception() -> None:
    """The fixed-torus refusal must not disappear from the totality audit."""
    with pytest.raises(esolangs.GeneratorCapError, match="at most thirteen inputs"):
        esolangs.generate("Befunge", "01" * 8192)
    assert "exception" in load().by_name()["Befunge"].labels
