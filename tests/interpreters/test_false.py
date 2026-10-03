"""Execution tests for the FALSE interpreter."""

import re

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.false import (
    _advance,
    _closers,
    _Machine,
    run,
)
from tests.interpreters.runner import run_program


def test_reading_an_unset_variable_halts() -> None:
    with pytest.raises(HaltError, match="read before it was stored"):
        run_program(run, "a;.")


@pytest.mark.parametrize(
    ("program", "message"),
    [
        ("[1", "unterminated '['"),
        ("1]", "closes a '[' that is not there"),
        ('"open', "unterminated '\"'"),
        ("{open", "unterminated '{'"),
        ("1'", "cannot end in"),
    ],
)
def test_a_malformed_program_is_refused(program: str, message: str) -> None:
    with pytest.raises(ValueError, match=re.escape(message)):
        run_program(run, program)


def test_dividing_by_zero_halts() -> None:
    with pytest.raises(HaltError, match="divides by zero"):
        run_program(run, "1 0/.")


def test_computing_on_a_lambda_halts() -> None:
    with pytest.raises(HaltError, match="is a lambda"):
        run_program(run, "1[]+.")


def test_running_a_number_halts() -> None:
    with pytest.raises(HaltError, match="is a number"):
        run_program(run, "1!")


def test_an_empty_stack_halts() -> None:
    with pytest.raises(HaltError, match="nothing to pop"):
        run_program(run, ".")


def test_a_bad_variable_reference_halts() -> None:
    with pytest.raises(HaltError, match="26 variable references"):
        run_program(run, "1 99:")


def test_the_pointer_stays_a_source_offset_inside_a_lambda() -> None:
    """A lambda is a span, so ``ip`` indexes the text the caller handed in."""
    program = "1[2.]!"
    machine = _Machine(program, ScriptedIO(""))
    seen = []
    while not machine.halted:
        seen.append(machine.ip)
        machine.step()
    assert all(at is not None and 0 <= at <= len(program) for at in seen)
    assert 2 in seen  # the body's '2', reached through '!'


def test_closers_pairs_every_bracket() -> None:
    assert _closers("[[]]") == {1: 2, 0: 3}


def test_picking_past_the_stack_halts() -> None:
    with pytest.raises(HaltError, match="which is not there"):
        run_program(run, "1 2 9\u00f8.")


def test_a_conditional_needs_a_lambda() -> None:
    with pytest.raises(HaltError, match="the top of the stack is a number"):
        run_program(run, "1 2?")


def test_a_loop_needs_two_lambdas() -> None:
    with pytest.raises(HaltError, match="one of these is a number"):
        run_program(run, "[1] 2#")


def test_advancing_a_finished_state_is_a_no_op() -> None:
    """No frames left is answered, not indexed: ``_advance`` is pure, so a
    caller stepping past the end gets the state back."""
    state = ((), (None,) * 26, ())
    assert _advance(state, "", {}) == (state, None)
