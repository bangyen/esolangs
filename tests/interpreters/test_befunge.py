"""Execution tests for the Befunge classic."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.befunge import _advance, _Machine, run
from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import Seeded
from esolangs.vm import run_until_halt
from tests.interpreters.runner import run_program


def run_befunge(program: str, stdin: str = "", rng: object = None) -> str:
    """Run a grid program and return its captured output."""
    return run_program(run, program.splitlines(), stdin, rng=rng)


def test_string_mode_pushes_and_commas_emit() -> None:
    assert run_befunge('"!dlroW ,olleH",,,,,,,,,,,,,@') == "Hello, World!"


def test_arithmetic_prints_with_the_reference_trailing_space() -> None:
    assert run_befunge("99*.@") == "81 "
    assert run_befunge("78*1+.@") == "57 "


def test_division_and_modulo_truncate_toward_zero() -> None:
    assert run_befunge("07-2 /.@") == "-3 "
    assert run_befunge("07-2 %.@") == "-1 "


def test_an_empty_stack_is_a_zero_divisor_like_any_other() -> None:
    """The implicit 0 and an explicit one take the same path.

    ``step`` used to ask for a result only when the stack was non-empty, so
    ``0/`` read while ``/`` -- popping the very same 0 -- halted instead.
    """
    assert run_befunge("/.@", "7\n") == "7 "
    assert run_befunge("%.@", "8\n") == "8 "
    assert run_befunge("0/.@", "7\n") == run_befunge("/.@", "7\n")


def test_a_zero_divisor_reads_the_result() -> None:
    assert run_befunge("10/.@", "7\n") == "7 "
    assert run_befunge("10%.@", "8\n") == "8 "
    for command in "/%":
        state = ((0, 0, 1, 0), ((command,),), (1, 0), False, False)
        with pytest.raises(HaltError, match="needs a result"):
            _advance(state)


def test_program_uses_the_80_by_25_torus() -> None:
    machine = _Machine(["<"], IO())
    machine.step()
    assert machine.ip == (0, 79, -1, 0)
    assert len(machine.state[1]) == 25
    assert len(machine.state[1][0]) == 80


def test_oversized_program_is_rejected() -> None:
    with pytest.raises(ValueError, match="80x25"):
        _Machine([" " * 81], IO())
    with pytest.raises(ValueError, match="80x25"):
        _Machine([" "] * 26, IO())


def test_both_conditionals_turn_the_pointer() -> None:
    """``_``/``|`` set a new heading from the popped value, then move."""
    for command, zero, nonzero in (
        ("_", (1, 0), (-1, 0)),
        ("|", (0, 1), (0, -1)),
    ):
        grid = ((command,),)
        moved, _ = _advance(((0, 0, 1, 0), grid, (0,), False, False))
        assert moved[0][2:4] == zero
        moved, _ = _advance(((0, 0, 1, 0), grid, (1,), False, False))
        assert moved[0][2:4] == nonzero


def test_bridge_skips_the_next_cell() -> None:
    # `#` steps over the 9, so the emitted value is 5.
    assert run_befunge("5#9.@") == "5 "


def test_put_writes_and_get_reads_the_grid() -> None:
    """``p`` pops y, x, v and writes a byte; ``g`` reads one back."""
    wrote, _ = _advance(((0, 0, 1, 0), (("p",), (" ",)), (64, 0, 1), False, False))
    assert wrote[1][1][0] == "@"
    read, _ = _advance(((0, 0, 1, 0), (("g",), ("@",)), (0, 1), False, False))
    assert read[2] == (64,)


def test_put_outside_the_grid_is_ignored() -> None:
    # The stack is (v, x, y) with y on top; both coordinates are off a 1x1 grid.
    moved, _ = _advance(((0, 0, 1, 0), (("p",),), (65, 5, 5), False, False))
    assert moved[1] == (("p",),)


def test_integer_and_character_input() -> None:
    assert run_befunge("&.@", "5\n") == "5 "
    assert run_befunge("~,@", "A\n") == "A"


def test_random_direction_uses_the_supplied_draw() -> None:
    # Right, down, left, up is the documented draw order; each moves one cell
    # from the `?` at (1,1).
    grid = ("...", ".?.", "...")
    state = ((1, 1, 1, 0), tuple(tuple(row) for row in grid), (), False, False)
    for direction, (x, y) in enumerate(((2, 1), (1, 2), (0, 1), (1, 0))):
        moved, _ = _advance(state, random_dir=direction)
        assert moved[0][:2] == (x, y)


def test_a_seeded_run_is_reproducible() -> None:
    program = "@@@\n@?@\n@@@"
    assert run_befunge(program, rng=Seeded(0)) == run_befunge(program, rng=Seeded(0))


def test_empty_program_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        run([], IO())


def test_a_repeated_push_uses_the_mutable_runtime_stack() -> None:
    """The one-cell source executes once per 80-column playfield lap."""
    machine = _Machine(["1"], IO())
    assert run_until_halt(machine, 20_000) is False
    assert machine.stack == [1] * 250


def test_a_done_state_is_its_own_successor() -> None:
    done = ((0, 0, 1, 0), (("@",),), (), False, True)
    assert _advance(done) == (done, None)


def test_complement_greater_than_and_discard() -> None:
    assert run_befunge("0!.@") == "1 "
    assert run_befunge("1!.@") == "0 "
    assert run_befunge("21`.@") == "1 "  # 2 > 1
    assert run_befunge("12`.@") == "0 "
    assert run_befunge("12$.@") == "1 "


def test_the_four_heading_commands_set_the_direction() -> None:
    for command, heading in (
        (">", (1, 0)),
        ("<", (-1, 0)),
        ("^", (0, -1)),
        ("v", (0, 1)),
    ):
        moved, _ = _advance(((0, 0, 0, 0), ((command,),), (), False, False))
        assert moved[0][2:4] == heading


def test_reads_past_the_end_halt() -> None:
    with pytest.raises(HaltError, match="random draw"):
        _advance(((0, 0, 1, 0), (("?",),), (), False, False))
    # ``_advance`` is called with no character supplied; the shell's read
    # raises EOF before this guard, so this is a direct-call contract.
    with pytest.raises(HaltError, match="no input left"):
        _advance(((0, 0, 1, 0), (("~",),), (), False, False))


def test_the_branching_protocol_forks_the_draw() -> None:
    """The hang search walks one state per direction ``?`` may take."""
    machine = _Machine(["?"], IO())
    start = machine.branching_snapshot()
    assert not machine.branching_halted(start)
    assert len(machine.branching_successors(start, 4)) == 4
    # A read cell cannot be forked, and a halted machine is its own successor.
    reading = _Machine(["~"], IO())
    assert reading.branching_successors(reading.branching_snapshot(), 4) is None
    # An ordinary command is deterministic: one successor.
    plain = _Machine(["0"], IO())
    assert len(plain.branching_successors(plain.branching_snapshot(), 4)) == 1
    halted = _Machine(["@"], IO())
    halted.step()
    final = halted.branching_snapshot()
    assert halted.branching_halted(final)
    assert halted.branching_successors(final, 4) == (final,)


def test_advance_refuses_input_the_shell_did_not_supply() -> None:
    empty = ((0, 0, 1, 0), (("&",),), (), False, False)
    with pytest.raises(HaltError, match="no input left"):
        _advance(empty)
