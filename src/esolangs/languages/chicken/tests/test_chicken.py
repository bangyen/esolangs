"""Tests for the Chicken interpreter."""

from pathlib import Path

import pytest

import esolangs
from esolangs.exceptions import HaltError, InterpreterLimitError
from esolangs.languages.chicken.interpreter import run
from esolangs.runtime.io import ScriptedIO
from tests.support.raises import assert_halts_with_hint, assert_rejected_with_hint

FIXTURES = Path(__file__).parent / "fixtures"


def _lines(*counts: int) -> str:
    return "".join(" ".join(["chicken"] * c) + "\n" for c in counts)


def _go(counts: tuple[int, ...], stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(_lines(*counts), io)
    return io.getvalue()


@pytest.mark.parametrize(
    ("name", "stdin", "output"),
    [
        ("hello", "", "Hello world"),
        ("hack_loop", "iiisdso", " 64 "),
        ("hack_loop", "dso", " 0 "),
        ("nan", "", "NaN"),
    ],
)
def test_wiki_programs_without_a_stated_output(name, stdin, output) -> None:
    """Outputs the page leaves unstated, checked against the programs' intent."""
    source = (FIXTURES / f"{name}.chicken").read_text()
    assert esolangs.run("Chicken", source, stdin=stdin, timeout=10) == output


def test_99_chickens_counts_down_from_the_input() -> None:
    source = (FIXTURES / "99_chickens.chicken").read_text()
    out = esolangs.run("Chicken", source, stdin="3", timeout=10)
    assert out == "3 chickens\n2 chickens\n1 chicken\nno chickens\n"
    assert esolangs.run("Chicken", source, stdin="99", timeout=10).count("\n") == 100


def test_empty_program_prints_the_pad() -> None:
    assert _go(()) == "0"


@pytest.mark.parametrize(
    ("counts", "output"),
    [
        ((12, 13, 2), "5"),  # numbers add
        ((12, 1, 2), "2chicken"),  # a string concatenates
        ((14, 13, 3), "1"),  # below minus top
        ((14, 13, 4), "12"),
        ((12, 12, 5), "true"),  # loose ==, printed as JavaScript prints it
        ((12, 1, 5), "false"),
        ((11, 1, 2, 11, 4), "NaN"),  # "1chicken" is not a number
        ((12, 1, 2, 1, 2), "2chickenchicken"),
        ((10 + 65, 9), "A"),
    ],
)
def test_operators_follow_javascript(counts, output) -> None:
    assert _go(counts) == output


def test_a_taken_jump_counts_from_the_next_cell() -> None:
    # cond 1, offset 2: skips the two pushes after the jump
    assert _go((11, 12, 8, 15, 16, 17)) == "7"
    assert _go((11, 12, 8, 15, 16)) == "0"  # lands on the pad
    assert _go((10, 12, 8, 15, 16, 17)) == "7"  # cond 0: falls through to 7
    assert _go((10, 12, 8, 15, 16)) == "6"


def test_a_string_is_truthy_even_when_it_reads_as_zero() -> None:
    # input[0] is "0": push 0, load input, push 1, jump over the push 5
    assert _go((10, 6, 1, 11, 8, 15, 16), "0") == "6"


def test_load_reads_the_input_and_the_stack() -> None:
    assert _go((11, 6, 1), "xy") == "y"
    assert _go((13, 6, 0)) == "6"  # cell 3 is the second line, 6 chickens
    assert _go((10 + 7, 6, 0)) == "undefined"
    assert _go((10 + 9, 6, 2)) == "undefined"  # cell 2 holds a number


def test_store_overwrites_a_cell_and_grows_the_array() -> None:
    assert _go((15, 10 + 20, 7, 10 + 20, 6, 0)) == "5"
    assert _go((15, 10 + 20, 7, 10 + 19, 6, 0)) == "undefined"


def test_running_off_the_end_exits_and_prints() -> None:
    assert _go((11, 13, 8)) == "0"  # lands past the array; the pad is on top


def test_input_is_the_whole_stdin() -> None:
    assert _go((12, 6, 1, 12, 6, 1, 2), "a\nbcd\n") == "bb"


def test_bad_words_are_rejected_with_a_repair_hint() -> None:
    assert_rejected_with_hint("Chicken", "chicken hen\n", "separated by spaces")


@pytest.mark.parametrize(
    ("counts", "message", "hint"),
    [
        ((10, 6, 0, 1, 2), "stack array", "numbers"),  # S[0] is the array
        ((10, 6, 99, 1), "undefined source", "source cell"),
        ((10, 10, 11, 3, 7), "non-index address", "non-negative"),
        ((11, 1, 8), "non-integer offset", "integer offset"),
    ],
)
def test_runtime_failures_carry_a_repair_hint(counts, message, hint) -> None:
    assert_halts_with_hint("Chicken", _lines(*counts), message, hint)


def test_code_point_past_unicode_halts() -> None:
    with pytest.raises(HaltError, match="code point"):
        _go((10 + 99, 10 + 99, 4, 10 + 99, 4, 10 + 99, 4, 9))


def test_a_huge_store_address_is_refused() -> None:
    nines = (10 + 9, 4) * 7
    with pytest.raises(InterpreterLimitError):
        _go((11, 10 + 9, *nines, 7))
