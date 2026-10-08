"""Unit tests for the B-tapemark interpreter."""

import pytest

from esolangs.interpreters.grid_based.b_tapemark import (
    _advance,
    _Grid,
    _load,
    _read,
    run,
)
from esolangs.interpreters.io import ScriptedIO


def execute(source: str, stdin: str = "") -> str:
    """Run ``source`` and return its output."""
    io = ScriptedIO(stdin)
    run(source, io)
    return io.getvalue()


def test_documented_cat() -> None:
    io = ScriptedIO("A\nB\n")
    with pytest.raises(EOFError):
        run("/>-+|\\\n\\    /", io)
    assert io.getvalue() == "A\nB\n"


def test_copy_and_character_input() -> None:
    assert execute(">*A+!") == "A"
    assert execute(">-+!", "Z\n") == "Z"


def test_quoted_text_is_blank() -> None:
    assert execute('>A"IGNORED"B!') == "AB"
    # a form feed is a column in a comment, not a row break (only LF/CRLF/CR split)
    assert execute('>A"\x0c"B!') == "AB"


def test_transition_does_not_mutate_its_input() -> None:
    state = _load(">*A!")
    advanced, output = _advance(state)
    assert state == _load(">*A!")
    assert advanced != state
    assert output is None


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("!", "exactly one start"),
        ("> <!", "exactly one start"),
        ('>"', "unmatched quote"),
        (">a!", "invalid.*'a'"),
        (">²!", "invalid.*'²'"),
    ],
)
def test_malformed_program(source: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        execute(source)


class TestTheGridIsAMapOfPoints:
    """The grid is keyed by point, and is still a value."""

    def test_a_blank_erases_the_mark(self) -> None:
        """Writing a blank removes the point rather than storing a space."""
        grid = _Grid({(0, 0): "A", (1, 0): "B"})
        cleared = grid.marked((0, 0), " ")
        assert cleared.at((0, 0)) == " "
        assert cleared.at((1, 0)) == "B"
        assert cleared == _Grid({(1, 0): "B"})

    def test_writing_leaves_the_original_alone(self) -> None:
        """A write returns a new grid; the old one is what a cycle compares."""
        grid = _Grid({(0, 0): "A"})
        assert grid.marked((0, 0), "Z").at((0, 0)) == "Z"
        assert grid.at((0, 0)) == "A"

    def test_a_missing_point_reads_blank(self) -> None:
        """Off the marks is a blank, not an error -- the scans rely on it."""
        assert _Grid({}).at((9, 9)) == " "


def test_a_halted_state_advances_to_itself() -> None:
    """``_advance`` on a halted state is a no-op, not a step off the end."""
    state = _load(">!")
    halted = _advance(_advance(state)[0])[0]
    while not halted.halted:
        halted = _advance(halted)[0]
    assert _advance(halted) == (halted, None)


def test_input_command_without_a_symbol_is_refused() -> None:
    """``-`` needs the byte the shell was supposed to have read for it."""
    state = _load(">-!")
    for _ in range(3):
        state = _advance(state)[0]
        if _read(state.grids[state.program], state.positions[state.program]) == "-":
            break
    with pytest.raises(ValueError, match="input symbol required"):
        _advance(state)


def test_copy_onto_an_occupied_cell_leaves_it() -> None:
    """``*`` copies only onto a blank data cell."""
    io = ScriptedIO("A\n")
    run(">-*+!", io)
    assert io.getvalue() == ""
