"""Execution tests for the Befunge classic."""

from ctypes import c_long, sizeof

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.befunge.interpreter import _advance, _Machine, run
from esolangs.runtime.io import IO
from esolangs.runtime.randomness import Seeded
from esolangs.vm import make_vm, run_until_halt, run_until_halt_or_cycle
from tests.interpreters.runner import run_program
from tests.support.raises import assert_halts_with_hint, assert_rejected_with_hint


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
    """The implicit 0 and an explicit one take the same path."""
    assert run_befunge("/.@", "7\n") == "7 "
    assert run_befunge("%.@", "8\n") == "8 "
    assert run_befunge("0/.@", "7\n") == run_befunge("/.@", "7\n")


def test_a_zero_divisor_with_nothing_to_read_halts() -> None:
    """The documented HaltError, through ``run`` rather than ``_advance``."""
    for program in ("10/.@", "/.@", "10%.@"):
        with pytest.raises(HaltError, match="needs a result"):
            run_befunge(program)
    with pytest.raises(EOFError):
        run_program(run, ["&.@"], suppress_eof=False)


def test_a_zero_divisor_reads_the_result() -> None:
    assert run_befunge("10/.@", "7\n") == "7 "
    assert run_befunge("10%.@", "8\n") == "8 "
    for command in "/%":
        state = ((0, 0, 1, 0), ((command,),), (0, (1, None)), False, False)
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
        _Machine([" " * 80 + "@"], IO())
    with pytest.raises(ValueError, match="80x25"):
        _Machine([" "] * 26, IO())


def test_both_conditionals_turn_the_pointer() -> None:
    """``_``/``|`` set a new heading from the popped value, then move."""
    for command, zero, nonzero in (
        ("_", (1, 0), (-1, 0)),
        ("|", (0, 1), (0, -1)),
    ):
        grid = ((command,),)
        moved, _ = _advance(((0, 0, 1, 0), grid, (0, None), False, False))
        assert moved[0][2:4] == zero
        moved, _ = _advance(((0, 0, 1, 0), grid, (1, None), False, False))
        assert moved[0][2:4] == nonzero


def test_bridge_skips_the_next_cell() -> None:
    # `#` steps over the 9, so the emitted value is 5.
    assert run_befunge("5#9.@") == "5 "


def test_put_writes_and_get_reads_the_grid() -> None:
    """``p`` pops y, x, v and writes a byte; ``g`` reads one back."""
    wrote, _ = _advance(
        ((0, 0, 1, 0), (("p",), (" ",)), (1, (0, (64, None))), False, False)
    )
    assert wrote[1][1][0] == "@"
    read, _ = _advance(((0, 0, 1, 0), (("g",), ("@",)), (1, (0, None)), False, False))
    assert read[2] == (64, None)


def test_put_outside_the_grid_is_ignored() -> None:
    # The stack is (v, x, y) with y on top; both coordinates are off a 1x1 grid.
    moved, _ = _advance(((0, 0, 1, 0), (("p",),), (5, (5, (65, None))), False, False))
    assert moved[1] == (("p",),)


def test_integer_and_character_input() -> None:
    assert run_befunge("&.@", "5\n") == "5 "
    assert run_befunge("~,@", "A\n") == "A"


def test_random_direction_uses_the_supplied_draw() -> None:
    # Right, down, left, up is the documented draw order; each moves one cell
    # from the `?` at (1,1).
    grid = ("...", ".?.", "...")
    state = ((1, 1, 1, 0), tuple(tuple(row) for row in grid), None, False, False)
    for direction, (x, y) in enumerate(((2, 1), (1, 2), (0, 1), (1, 0))):
        moved, _ = _advance(state, random_dir=direction)
        assert moved[0][:2] == (x, y)


def test_a_seeded_run_is_reproducible() -> None:
    program = "@@@\n@?@\n@@@"
    assert run_befunge(program, rng=Seeded(0)) == run_befunge(program, rng=Seeded(0))


def test_empty_program_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        run([], IO())


def test_a_repeated_push_keeps_the_persistent_stack() -> None:
    """The one-cell source executes once per 80-column playfield lap."""
    machine = _Machine(["1"], IO())
    assert run_until_halt(machine, 20_000) is False
    assert machine.stack == [1] * 250


def test_a_done_state_is_its_own_successor() -> None:
    done = ((0, 0, 1, 0), (("@",),), None, False, True)
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
        moved, _ = _advance(((0, 0, 0, 0), ((command,),), None, False, False))
        assert moved[0][2:4] == heading


def test_reads_past_the_end_halt() -> None:
    with pytest.raises(HaltError, match="random draw"):
        _advance(((0, 0, 1, 0), (("?",),), None, False, False))
    # ``_advance`` is called with no character supplied; the shell's read
    # raises EOF before this guard, so this is a direct-call contract.
    with pytest.raises(HaltError, match="no input left"):
        _advance(((0, 0, 1, 0), (("~",),), None, False, False))


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
    empty = ((0, 0, 1, 0), (("&",),), None, False, False)
    with pytest.raises(HaltError, match="no input left"):
        _advance(empty)


def test_string_mode_pushes_read_and_random_cells_as_characters() -> None:
    """Inside ``"``, ``/ ~ & ?`` are pushed, never read or drawn (Befunge-93)."""
    assert run_befunge('"?&~/",,,,@') == "/~&?"


def test_only_ascii_digits_push() -> None:
    """``²`` passes ``str.isdigit`` but is not a Befunge-93 digit: a no-op."""
    assert run_befunge("².@") == "0 "


def test_a_non_byte_source_cell_is_rejected() -> None:
    """Befunge-93 playfield cells are bytes; ``Ā`` (U+0100) cannot be one."""
    with pytest.raises(ValueError, match="bytes"):
        run_befunge("Ā@")


def test_a_value_past_signed_long_aborts() -> None:
    """81**16 overflows the reference's C long (UB there): abort, not a bignum."""
    with pytest.raises(HaltError, match="signed-long"):
        run_befunge("99*:*:*:*:*.@")


_LONG_BITS = sizeof(c_long) * 8  # 64, or 32 on Windows
# 2 squared to 2**(bits/2), times -(2**(bits/2 - 1)): -2**(bits-1), every push in range.
_MIN_LONG = "2" + ":*" * ((_LONG_BITS // 2).bit_length() - 1) + ":2/0\\-*"


def test_the_signed_long_range_is_inclusive_at_both_ends() -> None:
    """A C long's two ends are valid, one past the top is not, and 2**16 is no wrap."""
    low = -(1 << (_LONG_BITS - 1))
    assert run_befunge(_MIN_LONG + ".@") == f"{low} "
    assert run_befunge(_MIN_LONG + "1+0\\-.@") == f"{-low - 1} "
    with pytest.raises(HaltError, match="signed-long"):
        run_befunge(_MIN_LONG + "0\\-.@")
    assert run_befunge("99*:*:*.@") == "43046721 "


def test_a_byte_cell_at_the_top_of_the_range_is_accepted() -> None:
    """U+00FF is a byte: only cells above it are rejected."""
    assert run_befunge("\xff@") == ""


def test_get_at_the_first_column_past_the_grid_reads_zero() -> None:
    """x == 80 is off the 80-wide grid, so ``g`` pushes 0 rather than indexing."""
    assert run_befunge("88*88++0g.@") == "0 "


def test_the_branch_search_refuses_a_zero_divisor_read() -> None:
    """``/`` on an empty stack reads its result, so it cannot be forked."""
    machine = _Machine(["/"], IO())
    assert machine.branching_successors(machine.branching_snapshot(), 4) is None


def test_division_preserves_its_input_state() -> None:
    machine = _Machine(["42/1%"], IO())
    for _ in range(2):
        machine.step()
    before = machine.state
    first = _advance(before)
    assert _advance(before) == first
    assert before[2] == (2, (4, None))
    machine.step()
    assert machine.stack == [2]
    for _ in range(2):
        machine.step()
    assert machine.stack == [0]
    assert before[2] == (2, (4, None))


@pytest.mark.medium
def test_hints_for_bad_programs_and_input() -> None:
    assert_rejected_with_hint(
        "Befunge",
        "&@",
        "whitespace-separated decimal integer",
        stdin="oops",
        error=ValueError,
    )
    assert_halts_with_hint("Befunge", "10/.@", "divides by zero", "divisor")


def test_a_loop_that_never_draws_is_proved_by_the_snapshot_detector() -> None:
    """Befunge draws at ``?``; a program without one is still decidable.

    The detector refused every machine of a random language, this loop
    included, though a repeat with no draw in it proves the hang.
    """
    assert run_until_halt_or_cycle(make_vm("Befunge", ">v\n^<\n")) is False
    # A draw-free path to ``@`` is this run's halt too.
    assert run_until_halt_or_cycle(make_vm("Befunge", ">@\n")) is True
    # Once a draw can halt it, this run's own draw decides: refused, not guessed.
    with pytest.raises(TypeError, match="depends on its own draws"):
        run_until_halt_or_cycle(make_vm("Befunge", "?@@@@\n@\n"))
