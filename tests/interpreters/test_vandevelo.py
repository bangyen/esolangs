"""Tests for the Vandevelo interpreter."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.vandevelo import _Machine, run
from esolangs.vm import run_until_halt_or_cycle


def _halts(program: str, stdin: str = "") -> bool:
    return run_until_halt_or_cycle(_Machine(program, ScriptedIO(stdin)))


def test_strict_input_and_short_circuit() -> None:
    program = "x ~> Inp?\nx? == Nil? :: y?\n"
    assert _halts(program, "1\n")


def test_lazy_self_reference_is_a_cycle_only_when_selected() -> None:
    program = "loop -> loop?\nInp? :: loop?"
    assert _halts(program, "0\n")
    assert not _halts(program, "1\n")


def test_strict_and_negated_assignments() -> None:
    assert _halts("x ~!> Nil?\nx? :: Nil?")
    assert _halts("x -!> Nil?\nx? :: Nil?")


def test_inp_truth_values() -> None:
    for value in ("\n", "0\n", " \n"):
        assert _halts("Inp? :: missing?", value)
    with pytest.raises(ValueError, match="undefined variable"):
        run("Inp? :: missing?", ScriptedIO("yes\n"))


def test_invalid_expression_and_undefined_variable() -> None:
    with pytest.raises(ValueError, match="invalid expression"):
        _Machine("x -> nope", ScriptedIO())
    with pytest.raises(ValueError, match="undefined variable"):
        run("x?", ScriptedIO())


def test_eof_is_not_nil() -> None:
    with pytest.raises(EOFError):
        run("Inp?", ScriptedIO())
