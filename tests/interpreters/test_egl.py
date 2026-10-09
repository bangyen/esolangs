"""Unit tests for the EGL interpreter."""

import re
from functools import partial

import pytest

from esolangs.interpreters.grid_based.egl import _advance, run
from tests.interpreters.runner import run_program

execute = partial(run_program, run, suppress_eof=False)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param("10,1:++(>+++++<-)>=", "10", id="documented_examples"),
        pytest.param("2,2:+>++v+++#", "|1|2|\n|0|3|\n", id="grid_output"),
        pytest.param("2,1:+(->)=", "0", id="loop_tests_its_declaration_cell"),
        # ``^`` is the only mover the documented examples never exercise.
        pytest.param("10,10:v+^+=", "1", id="upward_movement"),
    ],
)
def test_output(code: str, expected: str) -> None:
    assert execute(code) == expected


def test_character_input() -> None:
    assert execute("1,1:x=", "42\n") == "52"


def test_dimensions_past_the_host_digit_limit_parse() -> None:
    """A 5001-digit width (leading zeros) is still the valid width 1."""
    assert execute("0" * 5000 + "1,1:+=") == "1"


def test_a_cursorless_read_loop_is_not_a_cycle() -> None:
    """Reads count in the snapshot: ``(x)`` runs to EOF, not a false cycle."""
    from esolangs.interpreters.grid_based.egl import _Machine
    from esolangs.vm import run_until_halt_or_cycle
    from tests.interpreters.cursorless_io import CursorlessIO

    machine = _Machine("1,1:+(x)", CursorlessIO("aaaaaaaa"))
    with pytest.raises(EOFError):
        run_until_halt_or_cycle(machine)


def test_reflections() -> None:
    """A reflection negates modulo the grid."""
    assert execute("2,3:+|=%=_=") == "111"
    assert execute("1,4:v+_=") == "0"
    assert execute("4,1:>+|=") == "0"
    assert execute("4,4:v>+%=") == "0"


def test_transition_does_not_mutate_its_input() -> None:
    state = (0, 0, 0, (0, 0), ())
    advanced, output = _advance(state, "+", {}, 2, 1)
    assert state == (0, 0, 0, (0, 0), ())
    assert advanced == (1, 0, 0, (1, 0), ())
    assert output is None


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("", "must begin"),
        ("0,1:", "dimensions must be positive"),
        ("1,1:(", "unmatched parenthesis"),
        ("1,1:>", "moved outside"),
    ],
)
def test_malformed_program(code: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        execute(code)


def test_a_close_without_an_open_is_rejected_at_the_transition() -> None:
    """``match_brackets`` rejects this at parse time, so only the pure
    transition can be asked what it does with a bare ``)``."""
    with pytest.raises(ValueError, match=re.escape("unmatched ')'")):
        _advance((0, 0, 0, (0,) * 4, ()), ")", {}, 2, 2)
