"""Underload's pure transition accepts an already halted state."""

from esolangs.interpreters.stack_based.underload import _advance


def test_pure_advance_accepts_a_halt_and_whitespace() -> None:
    assert _advance(("", 0, ())) == (("", 0, ()), None)
    assert _advance((" ", 0, ())) == ((" ", 1, ()), None)
