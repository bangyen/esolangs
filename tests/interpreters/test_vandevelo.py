"""Tests for the Vandevelo interpreter."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.vandevelo import (
    _advance,
    _Expr,
    _Machine,
    _State,
    _Statement,
    _statement,
    run,
)
from esolangs.vm import run_until_halt_or_cycle


def _halts(program: str, stdin: str = "") -> bool:
    return run_until_halt_or_cycle(_Machine(program, ScriptedIO(stdin)))


def test_strict_input_and_short_circuit() -> None:
    program = "x ~> Inp?\nx? == Nil? :: y?\n"
    assert _halts(program, "1\n")


def test_transition_is_a_pure_function_of_immutable_state() -> None:
    machine = _Machine("x ~> Nil?", ScriptedIO())
    initial = machine.state
    advanced = _advance(initial, machine.statements)

    assert _advance(initial, machine.statements) == advanced
    assert machine.state is initial
    assert hash(initial)


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


def test_a_comment_only_line_is_not_a_statement() -> None:
    assert _statement("-- nothing but a comment") is None


def _stacked(expression: _Expr, stage: int = 0, *, left: bool | None = None) -> _State:
    """A state parked mid-expression, which the parser never produces."""
    return _State(ind=0, part=0, store=(), stack=((expression, stage, left),))


def _step(state: _State, expression: _Expr, **kwargs: object) -> None:
    statement = _Statement(target=None, strict=True, negate=False, parts=(expression,))
    _advance(state, (statement,), **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("expression", "stage", "left", "message"),
    [
        (_Expr("not"), 0, None, "negation has no operand"),
        (_Expr("eq"), 0, None, "comparison has no left operand"),
        (_Expr("eq", left=_Expr("var", name="x")), 1, True, "no right operand"),
    ],
)
def test_a_missing_operand_is_refused(
    expression: _Expr, stage: int, *, left: bool | None, message: str
) -> None:
    """``_expr`` cannot build these, so the evaluator's guards are its own.

    They are kept because the fields are optional on the node type: without
    them a malformed node would read as ``None`` and evaluate silently.
    """
    with pytest.raises(ValueError, match=message):
        _step(_stacked(expression, stage, left=left), expression)


def test_inp_without_a_value_is_refused() -> None:
    """The evaluator asks for input a step before it uses it."""
    expression = _Expr("var", name="Inp")
    with pytest.raises(ValueError, match="input value required"):
        _step(_stacked(expression), expression, input_value=None)
