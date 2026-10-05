"""Tests for the Vandevelo interpreter."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.vandevelo import (
    _advance,
    _Expr,
    _Machine,
    _State,
    _Statement,
    run,
)
from esolangs.vm import run_until_halt_or_cycle


def _halts(program: str, stdin: str = "") -> bool:
    return run_until_halt_or_cycle(_Machine(program, ScriptedIO(stdin)))


def test_transition_is_a_pure_function_of_immutable_state() -> None:
    machine = _Machine("x ~> Nil?", ScriptedIO())
    initial = machine.state
    advanced = _advance(initial, machine.statements)

    assert _advance(initial, machine.statements) == advanced
    assert machine.state is initial


def test_invalid_expression_and_undefined_variable() -> None:
    with pytest.raises(ValueError, match="invalid expression"):
        _Machine("x -> nope", ScriptedIO())
    with pytest.raises(ValueError, match="undefined variable"):
        run("x?", ScriptedIO())


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
