"""Piet interpreter conformance tests."""

from pathlib import Path

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.piet import _command, _Machine, run
from esolangs.raster import Raster
from tests.interpreters.cursorless_io import PositionlessIO

LIGHT_RED = (255, 192, 192)
RED = (255, 0, 0)
DARK_RED = (192, 0, 0)
DARK_YELLOW = (192, 192, 0)
LIGHT_YELLOW = (255, 255, 192)
LIGHT_GREEN = (192, 255, 192)
LIGHT_CYAN = (192, 255, 255)
LIGHT_BLUE = (192, 192, 255)
DARK_BLUE = (0, 0, 192)
DARK_MAGENTA = (192, 0, 192)
YELLOW = (255, 255, 0)
MAGENTA = (255, 0, 255)
LIGHT_MAGENTA = (255, 192, 255)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


def raster(*rows: tuple[tuple[int, int, int], ...]) -> Raster:
    return Raster(rows)


def execute(program: Raster, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(program, io)
    return io.getvalue()


def test_push_and_output_number() -> None:
    # Three light-red codels push 3; red -> dark magenta outputs it.
    program = raster(
        (LIGHT_RED, BLACK, BLACK, DARK_MAGENTA),
        (LIGHT_RED, LIGHT_RED, RED, DARK_MAGENTA),
        (BLACK, BLACK, BLACK, DARK_MAGENTA),
    )
    assert execute(program) == "3"


def test_arithmetic_and_output() -> None:
    # push 3, push 1, add, output number
    program = raster(
        (LIGHT_RED, BLACK, BLACK, BLACK, BLACK, LIGHT_RED),
        (
            LIGHT_RED,
            LIGHT_RED,
            RED,
            DARK_RED,
            DARK_YELLOW,
            LIGHT_RED,
        ),
        (BLACK, BLACK, BLACK, BLACK, BLACK, LIGHT_RED),
    )
    assert execute(program) == "4"


def test_white_slide_executes_no_transition() -> None:
    program = raster(
        (LIGHT_RED, BLACK, BLACK, YELLOW),
        (LIGHT_RED, LIGHT_RED, WHITE, YELLOW),
        (BLACK, BLACK, BLACK, YELLOW),
    )
    assert execute(program) == ""


def test_white_slide_crosses_more_than_one_codel() -> None:
    from esolangs.interpreters.stack_based.piet import _slide

    program = raster((WHITE, WHITE, LIGHT_RED))
    assert _slide(program.rows, (0, 0), 0, -1) == ((2, 0), 0, -1)


def test_nonstandard_colour_is_white() -> None:
    program = raster(
        (LIGHT_RED, BLACK, BLACK, YELLOW),
        (LIGHT_RED, LIGHT_RED, (1, 2, 3), YELLOW),
        (BLACK, BLACK, BLACK, YELLOW),
    )
    assert execute(program) == ""


def test_white_turns_at_a_restriction() -> None:
    from esolangs.interpreters.stack_based.piet import _slide

    program = raster(
        (LIGHT_RED, WHITE, BLACK),
        (LIGHT_YELLOW, LIGHT_YELLOW, LIGHT_YELLOW),
    )
    assert _slide(program.rows, (1, 0), 0, -1) == ((1, 1), 1, 1)


def test_enclosed_white_terminates() -> None:
    from esolangs.interpreters.stack_based.piet import _slide

    program = raster(
        (BLACK, BLACK, BLACK),
        (BLACK, WHITE, BLACK),
        (BLACK, BLACK, BLACK),
    )
    assert _slide(program.rows, (1, 1), 0, -1) is None


def test_black_start_terminates() -> None:
    assert execute(raster((BLACK,))) == ""


def test_white_start_with_no_exit_terminates() -> None:
    assert execute(raster((WHITE,))) == ""


def test_white_start_and_trapped_slide_terminate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import esolangs.interpreters.stack_based.piet as piet

    slides = iter([((1, 0), 0, -1), None])
    monkeypatch.setattr(piet, "_slide", lambda *_args: next(slides))
    assert execute(raster((WHITE, LIGHT_RED))) == ""


@pytest.mark.parametrize("character", ["Z", "\n", "\0", "ā"])
@pytest.mark.parametrize("scale", [1, 3])
def test_input_character_and_output_character(character: str, scale: int) -> None:
    # in(char), then out(char)
    program = raster(
        (LIGHT_RED, BLACK, BLACK, DARK_BLUE),
        (LIGHT_RED, LIGHT_RED, LIGHT_MAGENTA, DARK_BLUE),
        (BLACK, BLACK, BLACK, DARK_BLUE),
    )
    loaded = Raster.from_png(program.upscaled(scale).to_png())
    assert execute(loaded, character) == character


def test_input_number_skips_whitespace_until_eof() -> None:
    """Whitespace without a number reaches EOF, which leaves the stack alone."""
    blank: list[int] = []
    _execute_command((4, 2), 1, blank, ScriptedIO("\n"))
    assert blank == []
    number: list[int] = []
    _execute_command((4, 2), 1, number, ScriptedIO("7\n"))
    assert number == [7]
    at_end: list[int] = []
    _execute_command((4, 2), 1, at_end, ScriptedIO(""))
    assert at_end == []


def test_public_api_runs_a_raster() -> None:
    program = raster(
        (LIGHT_RED, BLACK, BLACK, DARK_MAGENTA),
        (LIGHT_RED, LIGHT_RED, RED, DARK_MAGENTA),
        (BLACK, BLACK, BLACK, DARK_MAGENTA),
    )
    assert esolangs.describe("Piet")["source_kind"] == "raster"
    assert esolangs.run("Piet", program) == "3"


def test_public_api_loads_a_png(tmp_path: Path) -> None:
    program = raster(
        (LIGHT_RED, BLACK, BLACK, DARK_MAGENTA),
        (LIGHT_RED, LIGHT_RED, RED, DARK_MAGENTA),
        (BLACK, BLACK, BLACK, DARK_MAGENTA),
    )
    path = tmp_path / "program.png"
    path.write_bytes(program.to_png())
    assert esolangs.run("Piet", path) == "3"


@pytest.mark.parametrize(
    ("dp", "cc", "expected"),
    [
        (0, -1, (1, 0)),
        (0, 1, (1, 1)),
        (1, -1, (1, 1)),
        (1, 1, (0, 1)),
        (2, -1, (0, 1)),
        (2, 1, (0, 0)),
        (3, -1, (0, 0)),
        (3, 1, (1, 0)),
    ],
)
def test_codel_chooser_selects_the_documented_edge(
    dp: int, cc: int, expected: tuple[int, int]
) -> None:
    from esolangs.interpreters.stack_based.piet import _exit

    block = {(0, 0), (0, 1), (1, 0), (1, 1)}
    assert _exit(block, dp, cc) == expected


@pytest.mark.parametrize(
    ("change", "before", "after"),
    [
        ((0, 1), [], [7]),
        ((0, 2), [1], []),
        ((1, 0), [8, 3], [11]),
        ((1, 1), [8, 3], [5]),
        ((1, 2), [8, 3], [24]),
        ((2, 0), [-8, 3], [-3]),
        ((2, 1), [-8, 3], [1]),
        ((2, 2), [9], [0]),
        ((2, 2), [0], [1]),
        ((3, 0), [8, 3], [1]),
        ((4, 0), [8], [8, 8]),
        ((4, 1), [1, 2, 3, 3, 1], [3, 1, 2]),
    ],
)
def test_stack_commands(
    change: tuple[int, int], before: list[int], after: list[int]
) -> None:
    io = ScriptedIO()
    stack = before.copy()
    assert _execute_command(change, 7, stack, io) == (0, 0)
    assert stack == after


def test_pointer_and_switch_return_control_changes() -> None:
    io = ScriptedIO()
    stack = [-1, 3]
    assert _execute_command((3, 1), 1, stack, io) == (3, 0)
    assert _execute_command((3, 2), 1, stack, io) == (0, -1)


def test_empty_pointer_and_switch_are_ignored() -> None:
    io = ScriptedIO()
    assert _execute_command((3, 1), 1, [], io) == (0, 0)
    assert _execute_command((3, 2), 1, [], io) == (0, 0)


def test_invalid_commands_leave_the_stack_unchanged() -> None:
    io = ScriptedIO()
    for change, stack in [((1, 0), [1]), ((2, 0), [4, 0]), ((4, 1), [1, -2])]:
        before = stack.copy()
        _execute_command(change, 1, stack, io)
        assert stack == before


@pytest.mark.parametrize("change", [(0, 2), (2, 2), (4, 0), (5, 1), (5, 2)])
def test_empty_unary_commands_are_ignored(change: tuple[int, int]) -> None:
    stack: list[int] = []
    _execute_command(change, 1, stack, ScriptedIO())
    assert stack == []


def test_zero_roll_and_shallow_roll_are_ignored() -> None:
    io = ScriptedIO()
    zero = [1, 2, 2, 0]
    _execute_command((4, 1), 1, zero, io)
    assert zero == [1, 2]
    shallow = [1]
    _execute_command((4, 1), 1, shallow, io)
    assert shallow == [1]


def test_a_depth_zero_roll_pops_its_operands() -> None:
    """The wiki: roll "pops the top two values", then rotates the top 0."""
    stack = [5, 0, 3]
    _execute_command((4, 1), 1, stack, ScriptedIO())
    assert stack == [5]


def test_the_wiki_roll_example() -> None:
    """1,2,3 then push 3 and 1, roll: 3,1,2."""
    stack = [1, 2, 3, 3, 1]
    _execute_command((4, 1), 1, stack, ScriptedIO())
    assert stack == [3, 1, 2]


def test_switch_transition_changes_the_run_codel_chooser() -> None:
    program = raster(
        (LIGHT_RED, BLACK, BLACK, LIGHT_CYAN),
        (LIGHT_RED, LIGHT_RED, RED, LIGHT_CYAN),
        (BLACK, BLACK, BLACK, LIGHT_CYAN),
    )
    assert execute(program) == ""


def test_number_input_and_output() -> None:
    io = ScriptedIO("42\n")
    stack: list[int] = []
    _execute_command((4, 2), 1, stack, io)
    _execute_command((5, 1), 1, stack, io)
    assert io.getvalue() == "42"


@pytest.mark.parametrize("token", ["no", "1_0", "١٢"])
def test_invalid_and_exhausted_input_are_ignored(token: str) -> None:
    # Python's int reads "1_0" and Arabic-Indic digits; npiet reads neither.
    stack: list[int] = []
    _execute_command((4, 2), 1, stack, ScriptedIO(token + "\n"))
    _execute_command((5, 0), 1, stack, ScriptedIO())
    assert stack == []


def _execute_command(change, size, stack, io):
    before = tuple(stack)
    after, dp, cc, effect = _command(change, size, before)
    assert before == tuple(stack)
    stack[:] = _Machine.perform_io(after, effect, io)
    return dp, cc


def test_commands_are_repeatable_and_only_request_io() -> None:
    stack = (3, 5)
    assert _command((1, 0), 1, stack) == ((8,), 0, 0, None)
    assert _command((1, 0), 1, stack) == ((8,), 0, 0, None)
    assert _command((5, 1), 1, stack) == ((3,), 0, 0, ("write_num", 5))
    assert _command((4, 2), 1, stack) == (stack, 0, 0, ("read_num", 0))
    assert stack == (3, 5)


def test_halted_transition_preserves_state() -> None:
    from esolangs.interpreters.stack_based.piet import _advance

    state = ((0, 0), 0, -1, (3, 5), True)
    assert _advance(state, ((BLACK,),)) == (state, None)


def test_numeric_and_character_commands_share_the_input_cursor() -> None:
    source = ScriptedIO("A -7\nB")
    stack: list[int] = []
    _execute_command((5, 0), 1, stack, source)
    _execute_command((4, 2), 1, stack, source)
    _execute_command((5, 0), 1, stack, source)
    _execute_command((5, 0), 1, stack, source)
    assert stack == [65, -7, 10, 66]
    assert source.position() == 6
    _execute_command((5, 0), 1, stack, source)
    assert stack == [65, -7, 10, 66]


def test_a_read_loop_on_a_cursorless_port_runs_to_eof() -> None:
    """A port with no cursor reports position 0; the snapshot counts reads."""
    from esolangs.vm import run_until_halt_or_cycle

    io = PositionlessIO("x " * 10)
    machine = _Machine(raster((LIGHT_RED, DARK_BLUE)), io)
    assert not run_until_halt_or_cycle(machine, limit=1000)
    assert ScriptedIO.position(io) == 20  # every token was read


_WIKI = Path(__file__).parents[1] / "fixtures" / "piet"


def _stepped(name: str, stdin: str, steps: int) -> _Machine:
    raster_ = Raster.from_png((_WIKI / name).read_bytes())
    machine = _Machine(raster_, ScriptedIO(stdin))
    for _ in range(steps):
        if machine.halted:
            break
        machine.step()
    return machine


def test_wiki_hello_world_as_npiet_runs_it() -> None:
    """The caption says "Hello World!"; the image, under npiet too, prints this."""
    machine = _stepped("hello_world.png", "", 2000)
    assert machine.io.getvalue() == "Hello world\x1d"
    assert not machine.halted


def test_wiki_truth_machine_zero_halts() -> None:
    machine = _stepped("truth_machine.png", "0", 200)
    assert (machine.io.getvalue(), machine.halted) == ("0", True)


def test_wiki_truth_machine_one_repeats() -> None:
    machine = _stepped("truth_machine.png", "1", 500)
    assert not machine.halted
    assert set(machine.io.getvalue()) == {"1"}
    assert len(machine.io.getvalue()) > 20


def test_wiki_looping_counter_draws_its_triangle() -> None:
    """A 10x10-codel image at 50px per codel: rows of 1s, one longer each."""
    machine = _stepped("looping_counter.png", "", 3000)
    lines = machine.io.getvalue().split("\n")[:8]
    assert lines == ["1" * k for k in range(1, 9)]
