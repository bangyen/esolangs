"""Execution tests for the FALSE interpreter."""

import re

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.false import (
    _advance,
    _Machine,
    run,
)
from tests.interpreters.runner import run_program
from tests.raises import assert_halts_with_hint, assert_rejected_with_hint


@pytest.mark.parametrize(
    ("program", "message"),
    [
        pytest.param(
            "a;.", "read before it was stored", id="reading_an_unset_variable_halts"
        ),
        pytest.param("1 0/.", "divides by zero", id="dividing_by_zero_halts"),
        pytest.param("1[]+.", "is a lambda", id="computing_on_a_lambda_halts"),
        pytest.param(
            "1 99:", "26 variable references", id="a_bad_variable_reference_halts"
        ),
        pytest.param(
            "1 2?",
            "the top of the stack is a number",
            id="a_conditional_needs_a_lambda",
        ),
        pytest.param(
            "[1] 2#", "one of these is a number", id="a_loop_needs_two_lambdas"
        ),
        pytest.param("1!", "'!' runs a lambda", id="a_bang_needs_a_lambda"),
    ],
)
def test_halts(program: str, message: str) -> None:
    with pytest.raises(HaltError, match=message):
        run_program(run, program)


def test_arithmetic_prints_a_number() -> None:
    assert run_program(run, "1 2+.") == "3"
    assert run_program(run, "7 2/.") == "3"
    assert run_program(run, "7_ 2/.") == "-3"  # truncates toward zero


def test_comparison_is_minus_one_for_true() -> None:
    assert run_program(run, "2 1>.") == "-1"
    assert run_program(run, "1 2>.") == "0"
    assert run_program(run, "3 3=.") == "-1"


def test_a_lambda_runs_on_demand() -> None:
    assert run_program(run, "[1+]f:3f;!.") == "4"
    assert run_program(run, '1["yes"]?0["no"]?') == "yes"


def test_the_stack_shufflers() -> None:
    assert run_program(run, "1 2 3@...") == "132"  # rot: a b c -> b c a
    assert run_program(run, "1 2\\..") == "12"
    assert run_program(run, "7 8 0O.") == "8"  # pick counts from zero
    assert run_program(run, "7 8 1O.") == "7"
    assert run_program(run, "1 2%.") == "1"  # '%' drops


def test_a_read_preserves_newline() -> None:
    assert run_program(run, "^'0-.", "1\n") == "1"
    assert run_program(run, "^.", "\n") == "10"


def test_a_read_past_the_end_is_the_specs_minus_one() -> None:
    """``^`` answers -1 at end of input rather than letting EOF escape."""
    assert run_program(run, "^.", suppress_eof=False) == "-1"
    # The reference's cat loop: read until -1, printing each character.
    assert run_program(run, "[^$1_=~][,]#%", "A\nB\n", suppress_eof=False) == "A\nB\n"


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


@pytest.mark.parametrize(
    ("literal", "expected"),
    [
        ("2147483647", "2147483647"),
        ("2147483648", "-2147483648"),
        ("4294967295", "-1"),
        ("4294967296", "0"),
    ],
)
def test_literals_wrap_to_signed_32_bits(literal: str, expected: str) -> None:
    assert run_program(run, literal + ".") == expected


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


def test_only_ascii_digits_make_a_literal() -> None:
    """``²`` and ``٣`` pass ``str.isdigit`` but are unknown, so ignored."""
    assert run_program(run, "1\u00b2.") == "1"
    assert run_program(run, "1\u0663.") == "1"


def test_a_finished_loop_has_consumed_its_flag() -> None:
    """The stack view retires a spent ``#``, as ``halted`` already did."""
    machine = _Machine("[0][]#", ScriptedIO())
    while not machine.halted:
        machine.step()
    assert machine.stack == []


def test_advancing_a_finished_state_is_a_no_op() -> None:
    """No frames left is answered, not indexed: ``_advance`` is pure, so a
    caller stepping past the end gets the state back."""
    state = ((), (None,) * 26, ())
    assert _advance(state, "", {}) == (state, None)


def test_bitwise_or_and_pick_beyond_the_stack() -> None:
    assert run_program(run, "5 2|.") == "7"
    with pytest.raises(HaltError, match="which is not there"):
        run_program(run, "1 5ø")


@pytest.mark.medium
def test_bad_programs_carry_a_repair_hint() -> None:
    assert_rejected_with_hint("FALSE", "[", "close the lambda")
    assert_halts_with_hint("FALSE", "%", "stack is empty", "push a value")
