"""Execution tests for Befunge-98: unbounded Funge-space and the 98 core."""

import pytest

from esolangs.interpreters.grid_based.befunge_98 import _char, _Fixed, _Machine, run
from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.runner import run_program


def run98(program: str, stdin: str = "") -> str:
    """Run a grid program and return its captured output."""
    return run_program(run, program.split("\n"), stdin)


def machine(program: str, stdin: str = "") -> _Machine:
    return _Machine(program.split("\n"), ScriptedIO(stdin))


@pytest.mark.parametrize(
    ("program", "output"),
    [
        # The wiki's two Hello World programs.
        ('<v"Hello World!"\n >:v\n ^,_@', "Hello World!"),
        (
            'v>,vzzzzzzzzzzzzzzzz\n<|:<"Hello, world!"0\n@<zzzzzzzzzzzzzzzzzz',
            "Hello, world!",
        ),
        # Lahey wrap: west off column 0 re-enters at the box's east edge.
        ("<@.1", "1 "),
        ("f.a.95*.52-.@", "15 10 45 3 "),
        # Division truncates toward zero; by zero pushes 0.
        ("07-2/.07-2%.@", "-3 -1 "),
        ("50/.50%.72/.72%.@", "0 0 3 1 "),
        ("52`.25`.0!.5!.@", "1 0 1 0 "),
        ("12\\..1:..12$.123n.@", "1 2 1 1 1 0 "),
        # One space a run in string mode.
        ('"a   b"...@', "98 32 97 "),
        ("1#..@", "1 "),
        ("2j12.@", "0 "),
        ("1;2.;.@", "1 "),
        ("'A.'A,@", "65 A"),
        ("5s 20g.@", "5 "),
        ("9900p00g.@", "9 "),
        # p of a space empties the cell, and g of an empty cell reads 32.
        ("' 00p00g.99g.@", "32 32 "),
        # k runs its target n times in place, then the IP meets it once more.
        ("1232k...@", "3 2 1 0 0 "),
        ("10k.@", ""),
        # k's target skips a ;-region; a k that halts stops iterating.
        ("12k;z;.@", "1 0 0 "),
        ("2k@", ""),
        ("1v @\n >.^", "1 "),
        ("v\n1\n_@.", "0 "),
        ("0|\n .\n @", "0 "),
        ("1|\n @\n .", "0 "),
        ("[@\n.\n1", "1 "),
        ("]\n1\n.\n@", "1 "),
        ("r@.2", "2 "),
        ("11x\n   .\n    @", "0 "),
        # Unimplemented cells reflect: A-Z, ( and ) after their operands.
        ("A@.2", "2 "),
        ("0(@.1", "1 "),
        ("71(@.1", "1 "),
        ("t@.3", "3 "),
        # Stack stack: { moves a block to the new TOSS, } moves it back.
        ("1232{2}...@", "3 2 1 "),
        ("53{...@", "5 0 0 "),
        ("5 1{ 1u..@", "0 5 "),
        ("1{ 2 01-u 0}.@", "0 "),
        ("12-{0}...@", "0 0 0 "),
        ("1{ 01-}.@", "0 "),
        # } and u with no SOSS reflect.
        ("}@.1", "1 "),
        ("u@.1", "1 "),
        # y: 1 is flags, 3 the handprint, 7 the dimensions; past its own
        # table it picks from the stack.
        ("1y.3y.7y.0y.@", "0 1163087692 2 0 "),
        ("793*y.@", "7 "),
        ("94*y.@", "0 "),
    ],
)
def test_programs(program: str, output: str) -> None:
    assert run98(program) == output


def test_input_reads_tokens_and_reflects_at_eof() -> None:
    assert run98("&&+.@", "2 3") == "5 "
    assert run98("~.@", "A") == "65 "
    # Reflected, the IP wraps west onto ``@``: no error reaches the caller.
    assert run98("&.@") == ""
    assert run98("~.@") == ""


def test_q_returns_its_exit_code() -> None:
    assert run(["7q"], ScriptedIO("")) == 7
    assert run(["@"], ScriptedIO("")) == 0


def test_an_empty_program_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        machine("\n")


def test_a_value_outside_unicode_is_no_command() -> None:
    """NUL, not "": an empty string is a substring of every command set."""
    assert _char(-1) == _char(0x110000) == "\0"
    assert _char(ord("k")) == "k"


@pytest.mark.parametrize(
    ("program", "output"),
    [
        # a < b turns left (north, wrapping to '.' then '@'); a > b turns
        # right (south); equal goes on.  A wrong turn halts silently.
        ("12w\n  @\n  .", "0 "),
        ("21w\n  .\n  @", "0 "),
        ("11w.@", "0 "),
    ],
)
def test_w_turns_by_comparison(program: str, output: str) -> None:
    assert run98(program) == output


@pytest.mark.parametrize(
    ("pos", "delta", "after"),
    [
        ((2, 2), (1, 1), (0, 0)),
        ((1, 2), (1, 1), (0, 1)),
        # Outside the box heading in: the empty gap is skipped.
        ((-5, 1), (1, 0), (0, 1)),
        # A line that never meets the box: the IP is lost and keeps going.
        ((-5, 9), (1, 0), (-4, 9)),
        ((-5, 3), (1, 1), (-4, 4)),
        ((1, 1), (0, 0), (1, 1)),
    ],
)
def test_lahey_wrap_in_every_regime(
    pos: tuple[int, int], delta: tuple[int, int], after: tuple[int, int]
) -> None:
    m = machine("zzz\nzzz\nzzz")
    m.pos, m.delta = pos, delta
    m.step()
    assert m.pos == after


def test_the_vm_views() -> None:
    m = machine("1.@")
    assert m.ip == (0, 0, 1, 0)
    m.step()
    assert m.stack == [1]
    before = m.snapshot()
    assert before == m.snapshot()
    halted = stepped("1.@", 3)
    assert halted.halted
    assert halted.ip is None
    # Stepping past the halt changes nothing.
    assert stepped("@", 2).snapshot() == stepped("@", 1).snapshot()


def test_branching_forks_every_direction_of_a_draw() -> None:
    m = machine("?1.@")
    start = m.branching_snapshot()
    successors = m.branching_successors(start, 100)
    assert successors is not None
    assert sorted(state[0] for state in successors) == [(0, 0), (0, 0), (1, 0), (3, 0)]
    assert not m.branching_halted(start)
    halted = m.branching_successors(successors[2], 100)
    assert halted is not None
    assert m.branching_halted(halted[0])
    assert m.branching_successors(halted[0], 100) == (halted[0],)


def test_branching_cannot_fork_a_read() -> None:
    assert (
        machine("&@").branching_successors(machine("&@").branching_snapshot(), 9)
        is None
    )
    m = machine("1k&@")
    m.step()
    assert m.branching_successors(m.branching_snapshot(), 9) is None
    m = machine("1k?@")
    m.step()
    assert m.branching_successors(m.branching_snapshot(), 9) is None


def test_string_mode_steps_without_forking() -> None:
    m = machine('"?"@')
    m.step()
    successors = m.branching_successors(m.branching_snapshot(), 9)
    assert successors is not None
    assert len(successors) == 1


def test_a_write_after_a_snapshot_leaves_the_branch_state_alone() -> None:
    m = machine("500p@")
    frozen = m.branching_snapshot()
    for _ in range(4):
        m.step()
    assert m.space[(0, 0)] == 5
    assert frozen[4][(0, 0)] == ord("5")


HANDPRINT = 0x45534F4C
#: y's table for a bare one-stack machine, pushed bottom to top: environment
#: and command line (three nulls), stack sizes, count, time, date, then the
#: box span, least point, storage offset, delta and position, then the rest.
TAIL = [0, 0, 2, 0, 0, 1, HANDPRINT, 0, 0]


def test_y_pushes_its_whole_table() -> None:
    m = machine("0y@")
    m.step()
    m.step()
    assert m.stack == [0, 0, 0, 0, 1, 0, 0, 2, 0, 0, 0, 0, 0, 1, 0, 1, 0, *TAIL]


def test_y_sees_the_stack_stack_and_the_offset() -> None:
    m = machine("12 1{0y@")
    for _ in range(7):
        m.step()
    table = [0, 0, 0, 3, 1, 2, 0, 0, 7, 0, 0, 0, 5, 0, 1, 0, 6, 0, *TAIL]
    assert m.stack == [2, *table]


@pytest.mark.parametrize(
    ("program", "steps", "stacks", "offset"),
    [
        ("1234 2{", 7, [[1, 2, 0, 0], [3, 4]], (7, 0)),
        ("1234 2{ 1}", 10, [[1, 2, 4]], (0, 0)),
        ("5 01-{", 6, [[5, 0, 0, 0], []], (6, 0)),
        ("53{", 3, [[0, 0], [0, 0, 5]], (3, 0)),
        ("1{ 3}", 5, [[0, 0, 0]], (0, 0)),
        ("78 5 1{ 9 01-}", 14, [[7]], (0, 0)),
        ("123 1{ 3u", 9, [[1], [3, 0, 0, 2]], (6, 0)),
        ("1 0{ 45 02-u", 12, [[1, 0, 0, 5, 4], []], (4, 0)),
        # A block wider than the stack takes all of it, zeros beneath.
        ("123 5{", 6, [[0, 0], [0, 0, 1, 2, 3]], (6, 0)),
        ("0{ 12 3}", 8, [[0, 1, 2]], (0, 0)),
        # u past the SOSS's bottom transfers zeros.
        ("0{ 3u", 5, [[], [0, 0, 0]], (2, 0)),
        # u moves between the top two of three stacks.
        ("1 0{ 0{ 1u", 10, [[1, 0, 0], [4], [0]], (7, 0)),
        # The offset { sets is the next cell along a vertical delta too.
        ("v\n0\n{", 3, [[0, 0], []], (0, 3)),
    ],
)
def test_the_stack_stack(
    program: str, steps: int, stacks: list[list[int]], offset: tuple[int, int]
) -> None:
    m = machine(program)
    for _ in range(steps):
        m.step()
    assert m.stacks == stacks
    assert m.offset == offset


@pytest.mark.parametrize(
    ("program", "output"),
    [
        # g and p are relative to the storage offset { sets.
        ("0{20g.@", "103 "),
        ("10g.@", "48 "),
        ("07-02-/.7 02-/.07-02-%.702-%.@", "3 -3 -1 1 "),
        ("55`.@", "0 "),
        # A leading space in string mode is pushed.
        ('" a"..@', "97 32 "),
        # Turns while heading south: right is west, so the wrap meets '.'.
        ("v\n2\n1\nw@.", "0 "),
        ("v\n]@.", "0 "),
        ("51k.@", "5 0 "),
        # The 26th cell is y's own last, not the stack below it.
        ("7a2*6+y.@", "0 "),
    ],
)
def test_more_programs(program: str, output: str) -> None:
    assert run98(program) == output


def stepped(program: str, steps: int, **state: object) -> _Machine:
    """Return ``program`` after ``steps`` steps from the given IP state."""
    m = machine(program)
    for name, value in state.items():
        setattr(m, name, value)
    for _ in range(steps):
        m.step()
    return m


def test_j_scales_the_delta() -> None:
    assert stepped("v\n2\nj\n1\n2\n.\n@", 3).pos == (0, 5)
    assert stepped("1zjzzzzzzz", 2, delta=(2, 0)).pos == (6, 0)


def test_g_and_p_add_both_offset_axes() -> None:
    assert stepped("00g\n\nzzz", 3, offset=(1, 2)).stack == [ord("z")]
    assert stepped("900p", 4, offset=(1, 2)).space[(1, 2)] == 9


def test_parentheses_pop_their_operands() -> None:
    assert stepped("971(", 4).stack == [9]
    assert stepped("90(", 3).stack == [9]


def test_wrap_and_loss_on_an_off_origin_box() -> None:
    assert stepped("  zz\n  zz", 1, pos=(3, 0)).pos == (2, 0)
    assert stepped("z", 1, pos=(-5, 9), delta=(0, 1)).pos == (-5, 10)


def test_y_reports_an_off_origin_box() -> None:
    m = stepped("\n  0y@", 2, pos=(2, 1))
    assert m.stack == [0, 0, 0, 0, 1, 0, 0, 2, 0, 2, 1, 0, 0, 1, 0, 3, 1, *TAIL]
    assert stepped("1y@", 2).stack == [0]


def test_question_mark_draws_one_of_four() -> None:
    class Recording:
        def __init__(self) -> None:
            self.uppers: list[int] = []

        def randbelow(self, upper: int) -> int:
            self.uppers.append(upper)
            return 0

    draws = Recording()
    run_program(run, ["?@"], rng=draws)
    assert draws.uppers == [4]


def test_branching_steps_skipped_and_reading_cells_plainly() -> None:
    m = stepped(";?;@", 1)
    assert len(m.branching_successors(m.branching_snapshot(), 9) or ()) == 1
    assert (
        machine("~@").branching_successors(machine("~@").branching_snapshot(), 9)
        is None
    )


def test_the_empty_program_error_names_the_fix() -> None:
    # pytest matches the message and its notes joined by newlines.
    exact = "^Befunge-98 program cannot be empty\nhint: "
    with pytest.raises(ValueError, match=exact) as caught:
        machine("")
    assert caught.value.__notes__ == [
        "hint: provide at least one cell; @ halts immediately"
    ]


def test_a_put_grows_a_box_whose_corners_differ_by_axis() -> None:
    # Box (0,5)-(3,5): its least y exceeds its greatest x, which an
    # emptiness test mixing the axes would misread as an empty box.
    m = stepped("\n\n\n\n\n7a0p", 4, pos=(0, 5))
    assert (m.low, m.high) == ((0, 0), (10, 5))


def test_the_box_tracks_written_cells_only() -> None:
    m = machine("  @\n\n   ")
    assert (m.low, m.high) == ((2, 0), (2, 0))
    m = machine("'A01-01-p@")
    for _ in range(9):
        m.step()
    assert (m.low, m.high) == ((-1, -1), (9, 0))
    assert m.space[(-1, -1)] == 65
    # Writing a space empties the cell but never shrinks the box.
    m = machine("' 90p@")
    for _ in range(5):
        m.step()
    assert (9, 0) not in m.space
    assert (m.low, m.high) == ((0, 0), (5, 0))


@pytest.mark.parametrize(
    ("pos", "delta", "after"),
    [
        ((0, 0), (-1, -1), (2, 2)),
        ((5, 1), (-1, 0), (2, 1)),
        ((1, 0), (0, -1), (1, 2)),
        ((1, 1), (2, 0), (1, 1)),
        ((0, 1), (2, 0), (2, 1)),
    ],
)
def test_wrap_with_negative_and_long_deltas(
    pos: tuple[int, int], delta: tuple[int, int], after: tuple[int, int]
) -> None:
    m = machine("zzz\nzzz\nzzz")
    m.pos, m.delta = pos, delta
    m.step()
    assert m.pos == after


def test_r_reverses_both_axes() -> None:
    m = machine("r")
    m.delta = (2, -3)
    m.step()
    assert m.delta == (-2, 3)


def test_run_passes_its_draw_to_question_mark() -> None:
    assert run_program(run, ["?1.@"], rng=_Fixed(0)) == "1 "
    assert run_program(run, ["?1.@"], rng=_Fixed(2)) == ""


def test_successors_are_the_four_headings_in_draw_order() -> None:
    m = machine("?1.@")
    successors = m.branching_successors(m.branching_snapshot(), 9)
    assert successors is not None
    assert [state[:2] for state in successors] == [
        ((1, 0), (1, 0)),
        ((0, 0), (0, 1)),
        ((3, 0), (-1, 0)),
        ((0, 0), (0, -1)),
    ]


def test_a_branch_that_writes_leaves_its_parent_alone() -> None:
    m = machine("500p@")
    first = state = m.branching_snapshot()
    for _ in range(4):
        (state,) = m.branching_successors(state, 9) or ()
    assert state[4][(0, 0)] == 5
    assert first[4][(0, 0)] == ord("5")
    assert m.space[(0, 0)] == ord("5")
