"""Piet interpreter conformance tests."""

from pathlib import Path

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.piet import _command, _Machine, run
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


def test_invalid_and_exhausted_input_are_ignored() -> None:
    stack: list[int] = []
    _execute_command((4, 2), 1, stack, ScriptedIO("no\n"))
    _execute_command((5, 0), 1, stack, ScriptedIO())
    assert stack == []


def _execute_command(change, size, stack, io):
    before = tuple(stack)
    after, dp, cc, effect = _command(change, size, before)
    assert before == tuple(stack)
    stack[:] = _Machine.perform_io(after, effect, io)
    return (dp, cc)


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
