"""Unit tests for the Stun Step interpreter."""

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
        assert run_and_capture("-") == "0"
        assert run_and_capture("+--") == "0"

    def test_move_right_requires_nonzero_cell(self) -> None:
        assert run_and_capture(">") == "0"
        assert run_and_capture("+>-") == "1 0"

    def test_move_left_requires_nonzero_cell(self) -> None:
        assert run_and_capture("<") == "0"
        assert run_and_capture("+>+<-") == "0 2"


class TestStunStepHalting:
    def test_halts_when_current_cell_is_zero(self) -> None:
        assert run_and_capture("+>-") == "1 0"
        assert run_and_capture("++>--") == "2 0"

    def test_loops_back_to_start_when_nonzero(self) -> None:
        assert run_and_capture("<+<->>") == "1"


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

    def test_nul_truncates_the_program(self) -> None:
        assert run_and_capture("ab\x00cd") == "0"

    def test_left_below_start_overlaps_program_bytes(self) -> None:
        assert run_and_capture("++<--") == "2"
        assert run_and_capture("-+<<") == "1"
        assert run_and_capture("<->+") == "0 1"
