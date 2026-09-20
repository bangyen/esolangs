"""Execution tests for the interpreter-only Befunge classic."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.befunge import _advance, run
from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import Seeded
from tests.interpreters.runner import run_program


def run_befunge(program: str, stdin: str = "", rng: object = None) -> str:
    """Run a grid program and return its captured output."""
    return run_program(run, program.splitlines(), stdin, rng=rng)


def test_string_mode_pushes_and_commas_emit() -> None:
    assert run_befunge('"!dlroW ,olleH",,,,,,,,,,,,,@') == "Hello, World!"


def test_arithmetic_prints_with_the_reference_trailing_space() -> None:
    assert run_befunge("99*.@") == "81 "
    assert run_befunge("78*1+.@") == "57 "


def test_division_and_modulo_round_down() -> None:
    # -7 / 2 floors to -4 and -7 % 2 follows the divisor, as the wiki says.
    assert run_befunge("07-2 /.@") == "-4 "
    assert run_befunge("07-2 %.@") == "1 "


def test_a_zero_divisor_halts_with_a_message() -> None:
    for program in ("10/.@", "10%.@"):
        with pytest.raises(HaltError, match="zero"):
            run(program.splitlines(), IO())


def test_both_conditionals_turn_the_pointer() -> None:
    """``_``/``|`` set a new heading from the popped value, then move."""
    for command, zero, nonzero in (
        ("_", (1, 0), (-1, 0)),
        ("|", (0, 1), (0, -1)),
    ):
        grid = ((command,),)
        moved, _ = _advance((0, 0, 1, 0, grid, (0,), False, False))
        assert moved[2:4] == zero
        moved, _ = _advance((0, 0, 1, 0, grid, (1,), False, False))
        assert moved[2:4] == nonzero


def test_bridge_skips_the_next_cell() -> None:
    # `#` steps over the 9, so the emitted value is 5.
    assert run_befunge("5#9.@") == "5 "


def test_put_writes_and_get_reads_the_grid() -> None:
    """``p`` pops y, x, v and writes a byte; ``g`` reads one back."""
    wrote, _ = _advance((0, 0, 1, 0, (("p",), (" ",)), (64, 0, 1), False, False))
    assert wrote[4][1][0] == "@"
    read, _ = _advance((0, 0, 1, 0, (("g",), ("@",)), (0, 1), False, False))
    assert read[5] == (64,)


def test_integer_and_character_input() -> None:
    assert run_befunge("&.@", "5\n") == "5 "
    assert run_befunge("~,@", "A\n") == "A"


def test_random_direction_uses_the_supplied_draw() -> None:
    # Right, down, left, up is the documented draw order; each moves one cell
    # from the `?` at (1,1).
    grid = ("...", ".?.", "...")
    state = (1, 1, 1, 0, tuple(tuple(row) for row in grid), (), False, False)
    for direction, (x, y) in enumerate(((2, 1), (1, 2), (0, 1), (1, 0))):
        moved, _ = _advance(state, random_dir=direction)
        assert moved[:2] == (x, y)


def test_a_seeded_run_is_reproducible() -> None:
    program = "@@@\n@?@\n@@@"
    assert run_befunge(program, rng=Seeded(0)) == run_befunge(program, rng=Seeded(0))


def test_empty_program_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        run([], IO())


def test_a_done_state_is_its_own_successor() -> None:
    done = (0, 0, 1, 0, (("@",),), (), False, True)
    assert _advance(done) == (done, None)


def test_advance_refuses_input_the_shell_did_not_supply() -> None:
    empty = (0, 0, 1, 0, (("&",),), (), False, False)
    with pytest.raises(HaltError, match="no input left"):
        _advance(empty)
