"""Unit tests for the Stun Step interpreter.

Stun Step runs a tape of unbounded nonnegative integers (all cells are 1
except the one the pointer starts on, which is 0).  ``+``/``-`` adjust the
current cell, ``>``/``<`` move the pointer only while it is nonzero, and at
the end of the program the machine halts if the current cell is 0, else loops
back to the start.  Non-terminating programs run forever.
"""

import io
from contextlib import redirect_stdout

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.stun_step import run


def run_and_capture(code: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestStunStepCommands:
    def test_empty_program(self) -> None:
        assert run_and_capture("") == "0"

    def test_increment_and_decrement(self) -> None:
        assert run_and_capture("+-") == "0"
        assert run_and_capture("++--") == "0"
        assert run_and_capture("+++---") == "0"

    def test_decrement_clamps_at_zero(self) -> None:
        """Decrementing 0 is undefined per the wiki; we leave it at 0."""
        assert run_and_capture("-") == "0"
        assert run_and_capture("+--") == "0"

    def test_move_right_requires_nonzero_cell(self) -> None:
        assert run_and_capture(">") == "0"
        assert run_and_capture("+>-") == "1 0"

    def test_move_left_requires_nonzero_cell(self) -> None:
        assert run_and_capture("<") == "0"
        assert run_and_capture("+>+<-") == "0 2"

    def test_move_left_of_start(self) -> None:
        """The tape extends to negative positions too."""
        assert run_and_capture("++<--") == "0 2"


class TestStunStepHalting:
    def test_halts_when_current_cell_is_zero(self) -> None:
        assert run_and_capture("+>-") == "1 0"
        assert run_and_capture("++>--") == "2 0"
        assert run_and_capture("<+<->>") == "0 1"


class TestStunStepOutput:
    def test_multiple_cells(self) -> None:
        assert run_and_capture("+>++>--") == "1 3 0"
        assert run_and_capture(">+>+>-") == "1 2 0"

    def test_multidigit_values(self) -> None:
        assert run_and_capture("+++++++++++++>--") == "13 0"

    def test_no_trailing_separator(self) -> None:
        assert run_and_capture("+>-") == "1 0"
        assert not run_and_capture("+>-").endswith(" ")


class TestStunStepSourceHandling:
    def test_non_commands_are_ignored(self) -> None:
        assert run_and_capture("ab+cd-ef") == "0"
