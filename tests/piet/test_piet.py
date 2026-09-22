"""Piet interpreter conformance tests."""

from pathlib import Path

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.piet import _command, run
from esolangs.raster import Raster

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
    from esolangs.piet import _slide

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
    from esolangs.piet import _slide

    program = raster(
        (LIGHT_RED, WHITE, BLACK),
        (LIGHT_YELLOW, LIGHT_YELLOW, LIGHT_YELLOW),
    )
    assert _slide(program.rows, (1, 0), 0, -1) == ((1, 1), 1, 1)


def test_enclosed_white_terminates() -> None:
    from esolangs.piet import _slide

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
    import esolangs.piet as piet

    slides = iter([((1, 0), 0, -1), None])
    monkeypatch.setattr(piet, "_slide", lambda *_args: next(slides))
    assert execute(raster((WHITE, LIGHT_RED))) == ""


def test_input_character_and_output_character() -> None:
    # in(char), then out(char)
    program = raster(
        (LIGHT_RED, BLACK, BLACK, DARK_BLUE),
        (LIGHT_RED, LIGHT_RED, LIGHT_MAGENTA, DARK_BLUE),
        (BLACK, BLACK, BLACK, DARK_BLUE),
    )
    assert execute(program, "Z\n") == "Z"


def test_input_number_reads_a_blank_line_as_zero() -> None:
    """A blank line is the package's 0, not a dropped read.

    ``input_num`` is ``int(line)``, which raised on the empty string and was
    suppressed, so this command pushed nothing where the char command pushed
    0 -- contradicting the module's own "a blank line is a value".
    """
    blank: list[int] = []
    _command((4, 2), 1, blank, ScriptedIO("\n"))
    assert blank == [0]
    number: list[int] = []
    _command((4, 2), 1, number, ScriptedIO("7\n"))
    assert number == [7]
    at_end: list[int] = []
    _command((4, 2), 1, at_end, ScriptedIO(""))
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
    from esolangs.piet import _exit

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
    assert _command(change, 7, stack, io) == (0, 0)
    assert stack == after


def test_pointer_and_switch_return_control_changes() -> None:
    io = ScriptedIO()
    stack = [-1, 3]
    assert _command((3, 1), 1, stack, io) == (3, 0)
    assert _command((3, 2), 1, stack, io) == (0, -1)


def test_empty_pointer_and_switch_are_ignored() -> None:
    io = ScriptedIO()
    assert _command((3, 1), 1, [], io) == (0, 0)
    assert _command((3, 2), 1, [], io) == (0, 0)


def test_invalid_commands_leave_the_stack_unchanged() -> None:
    io = ScriptedIO()
    for change, stack in [((1, 0), [1]), ((2, 0), [4, 0]), ((4, 1), [1, -2])]:
        before = stack.copy()
        _command(change, 1, stack, io)
        assert stack == before


@pytest.mark.parametrize("change", [(0, 2), (2, 2), (4, 0), (5, 1), (5, 2)])
def test_empty_unary_commands_are_ignored(change: tuple[int, int]) -> None:
    stack: list[int] = []
    _command(change, 1, stack, ScriptedIO())
    assert stack == []


def test_zero_roll_and_shallow_roll_are_ignored() -> None:
    io = ScriptedIO()
    zero = [1, 2, 2, 0]
    _command((4, 1), 1, zero, io)
    assert zero == [1, 2]
    shallow = [1]
    _command((4, 1), 1, shallow, io)
    assert shallow == [1]


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
    _command((4, 2), 1, stack, io)
    _command((5, 1), 1, stack, io)
    assert io.getvalue() == "42"


def test_invalid_and_exhausted_input_are_ignored() -> None:
    stack: list[int] = []
    _command((4, 2), 1, stack, ScriptedIO("no\n"))
    _command((5, 0), 1, stack, ScriptedIO())
    assert stack == []
