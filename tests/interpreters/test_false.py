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


def test_a_string_is_printed_verbatim() -> None:
    assert run_program(run, '"Hello, world!"') == "Hello, world!"


def test_arithmetic_prints_a_number() -> None:
    assert run_program(run, "1 2+.") == "3"
    assert run_program(run, "7 2/.") == "3"
    assert run_program(run, "7_ 2/.") == "-3"  # truncates toward zero


def test_comparison_is_minus_one_for_true() -> None:
    assert run_program(run, "2 1>.") == "-1"
    assert run_program(run, "1 2>.") == "0"
    assert run_program(run, "3 3=.") == "-1"


def test_a_variable_round_trips() -> None:
    assert run_program(run, "5a:a;a;*.") == "25"


def test_reading_an_unset_variable_halts() -> None:
    with pytest.raises(HaltError, match="read before it was stored"):
        run_program(run, "a;.")


def test_a_lambda_runs_on_demand() -> None:
    assert run_program(run, "[1+]f:3f;!.") == "4"
    assert run_program(run, '1["yes"]?0["no"]?') == "yes"


def test_the_while_loop_counts_down() -> None:
    assert run_program(run, "5[$0=~][$.1-]#%") == "54321"


def test_the_stack_shufflers() -> None:
    assert run_program(run, "1 2 3@...") == "132"  # rot: a b c -> b c a
    assert run_program(run, "1 2\\..") == "12"
    assert run_program(run, "7 8 0O.") == "8"  # pick counts from zero
    assert run_program(run, "7 8 1O.") == "7"
    assert run_program(run, "1 2%.") == "1"  # '%' drops


def test_a_character_is_pushed_and_printed() -> None:
    assert run_program(run, "'A,") == "A"


def test_a_read_takes_the_first_character_of_a_line() -> None:
    assert run_program(run, "^'0-.", "1\n") == "1"
    assert run_program(run, "^.", "\n") == "0"  # an empty line reads as 0


def test_a_read_past_the_end_is_the_specs_minus_one() -> None:
    """``^`` answers -1 at end of input rather than letting EOF escape.

    ``suppress_eof=False`` so a leaked ``EOFError`` fails here instead of
    being swallowed into an empty output.
    """
    assert run_program(run, "^.", suppress_eof=False) == "-1"
    # The reference's cat loop: read until -1, printing each character.
    assert run_program(run, "[^$1_=~][,]#%", "A\nB\n", suppress_eof=False) == "AB"


def test_a_comment_is_skipped_and_its_brackets_do_not_nest() -> None:
    assert run_program(run, "{[}1.") == "1"


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


def test_arithmetic_wraps_to_signed_32_bits() -> None:
    assert run_program(run, "2147483647 1+.") == "-2147483648"


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


def test_literal_wrapping_applies_before_comparison() -> None:
    assert run_program(run, "2147483648 0>.") == "0"


def test_a_long_literal_does_not_hit_the_python_decimal_limit() -> None:
    assert run_program(run, "0" * 5000 + "4294967297.") == "1"


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


def test_an_empty_program_halts_at_once() -> None:
    assert run_program(run, "") == ""


def test_an_unknown_character_is_ignored() -> None:
    """``B`` flushes a buffer this package has not got, so it is a no-op."""
    assert run_program(run, "1.B") == "1"


def test_bitwise_operators_wrap_to_32_bits() -> None:
    assert run_program(run, "12 10&.") == "8"
    assert run_program(run, "12 10|.") == "14"


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
