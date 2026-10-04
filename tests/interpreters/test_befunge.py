"""Execution tests for the Befunge classic."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.befunge import _advance, _Machine, run
from esolangs.interpreters.io import IO
from tests.interpreters.runner import run_program


def run_befunge(program: str, stdin: str = "", rng: object = None) -> str:
    """Run a grid program and return its captured output."""
    return run_program(run, program.splitlines(), stdin, rng=rng)


def test_a_zero_divisor_with_nothing_to_read_halts() -> None:
    """The documented HaltError, through ``run`` rather than ``_advance``.

    ``step`` reads the result before ``_advance`` runs, so the exhausted
    input raised ``InputExhaustedError`` first and the HaltError below was
    unreachable from outside.  ``&`` is a plain read and still propagates.
    """
    for program in ("10/.@", "/.@", "10%.@"):
        with pytest.raises(HaltError, match="needs a result"):
            run_befunge(program)
    with pytest.raises(EOFError):
        run_program(run, ["&.@"], suppress_eof=False)


def test_oversized_program_is_rejected() -> None:
    with pytest.raises(ValueError, match="80x25"):
        _Machine([" " * 81], IO())
    with pytest.raises(ValueError, match="80x25"):
        _Machine([" "] * 26, IO())


def test_empty_program_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        run([], IO())


@pytest.mark.parametrize(
    ("command", "message"),
    [
        ("?", "random draw"),
        ("~", "no input left"),
        ("&", "no input left"),
        ("/", "needs a result"),
        ("%", "needs a result"),
    ],
)
def test_pure_transition_refuses_unsupplied_effects(command: str, message: str) -> None:
    state = ((0, 0, 1, 0), ((command,),), (), False, False)
    with pytest.raises(HaltError, match=message):
        _advance(state)
