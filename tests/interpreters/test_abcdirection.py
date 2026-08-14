"""Unit tests for the ABCDirection interpreter.

Tests cover the source-file terminator and comment mechanism, the grid
rules, the direction commands (``A``/``B``), the tape commands (``C``), the
queue commands (``D``), Boolfuck-style bit I/O, donut wrapping, and the
step limit.
"""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.abcdirection import run


def run_program(code: str, stdin: str = "", limit: int = 100_000) -> str:
    io = ScriptedIO(stdin)
    try:
        run(code, io, limit=limit)
    except EOFError:
        pass
    except HaltError:
        pass
    return io.getvalue()


def run_halts(code: str, stdin: str = "", limit: int = 100_000) -> None:
    io = ScriptedIO(stdin)
    with pytest.raises(HaltError):
        run(code, io, limit=limit)


# A column of eight C's: going down, each outputs the current tape cell (a
# zero), then the bottom D turns the pointer left into the D row, where D
# dequeues forever.  One byte of zeros, then the step limit fires.
ZERO_BYTE = "\n".join(["CBBBBB"] * 8 + ["DDDDDD"])

# The same for two bytes of zeros.
TWO_ZERO_BYTES = "\n".join(["CBBBBB"] * 16 + ["DDDDDD"])

# A width-8 clockwise rectangle: down column 0 (eight C's output), left and
# right through the corner A's on the bottom row, and up column 7 where the
# two D's read a byte of input (two bits per lap, LSB first).  The bottom
# row's grid width comes from the DDDDDD at position 2.
RECTANGLE = """\
BBBBBBBD
CBBBBBBB
CBBBBBBB
CBBBBBBB
CBBBBBBB
CBBBBBBB
CBBBBBBB
CBBBBBBB
ABBBBBBA
BBDDDDDD"""

# The width-6 figure-eight: C's on column 5 output, a C on the bottom row
# flips the tape, a D on the top row enqueues the cell, and the bottom D
# branches on the cell and queue before dequeueing along the D row.
QUEUE = """\
BBBBBD
BBBBBC
BBBBBC
BBBBBC
BBBBBC
ACBBBA
DDDDDD"""

# The width-6 figure-eight with no queue D: the first input bit (a 1 for
# ``A``) is read into the cell, so the bottom D-down passes straight through
# instead of turning left.
PASS_THROUGH = """\
BBBBBB
CBBBBB
CBBBBB
CBBBBB
CBBBBB
CBBBBB
CBBBBB
CBBBBB
ABBBBB
DDDDDD"""


class TestSourceFormat:
    def test_missing_terminator(self) -> None:
        with pytest.raises(ValueError, match="DDDDDD"):
            run_program("BBBBBB\nBBBBBB")

    def test_comment_after_terminator_is_ignored(self) -> None:
        program = "\n".join(
            [
                "CBBBBB",
                "CBBBBB",
                "CBBBBB",
                "CBBBBB",
                "CBBBBB",
                "CBBBBB",
                "CBBBBB",
                "CBBBBB",
                "DDDDDD anything goes here, even 123 and spaces",
            ]
        )
        run_halts(program)
        assert run_program(program) == "\x00"

    def test_reading_stops_at_first_terminator(self) -> None:
        # The extra D's after DDDDDD on the last line are a comment.
        program = "\n".join(["CBBBBB"] * 8 + ["DDDDDDDDDD"])
        run_halts(program)
        assert run_program(program) == "\x00"

    def test_non_abcd_cell_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="A, B, C, D"):
            run_program("CBBBBB\nCBBBBX\nDDDDDD")

    def test_short_row_is_not_a_rectangle(self) -> None:
        with pytest.raises(ValueError, match="rectangle"):
            run_program("CBBBBB\nCBBBB\nDDDDDD")

    def test_blank_line_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="rectangle"):
            run_program("CBBBBB\n\nDDDDDD")

    def test_long_rows_are_trimmed_to_the_grid_width(self) -> None:
        # The grid width comes from the terminator; extra trailing cells are
        # trimmed off each row.
        program = "CBBBBBBBB\n" + "CBBBBB\n" * 7 + "DDDDDD"
        run_halts(program)
        assert run_program(program) == "\x00"


class TestOutput:
    def test_zero_byte_then_step_limit(self) -> None:
        run_halts(ZERO_BYTE)
        assert run_program(ZERO_BYTE) == "\x00"

    def test_two_zero_bytes(self) -> None:
        run_halts(TWO_ZERO_BYTES)
        assert run_program(TWO_ZERO_BYTES) == "\x00\x00"

    def test_rectangle_outputs_the_input_bits(self) -> None:
        # Two input bits per lap; the second one wins the cell, so each byte
        # mirrors the previous lap's second bit (plus a leading zero from
        # the cell's initial state).
        assert run_program(RECTANGLE, "\xaa") == "\x80\xff\xff\xff"
        assert run_program(RECTANGLE, "\x00") == "\x00\x00\x00\x00"


class TestInput:
    def test_empty_input_raises_eof(self) -> None:
        io = ScriptedIO("")
        with pytest.raises(EOFError):
            run(RECTANGLE, io, limit=100_000)

    def test_empty_input_raises_eof_on_single_read(self) -> None:
        io = ScriptedIO("")
        with pytest.raises(EOFError):
            run(PASS_THROUGH, io, limit=100_000)


class TestControlFlow:
    def test_d_down_turns_left_on_zero_cell_and_empty_queue(self) -> None:
        # The zero column ends at a D going down; the empty queue sends the
        # pointer left along the D row, where each D dequeues into the cell.
        run_halts(ZERO_BYTE)

    def test_d_down_passes_straight_through_on_one_cell(self) -> None:
        # With the cell holding the first input bit (a 1), the bottom D goes
        # straight down and the loop continues past the D row.
        run_halts(PASS_THROUGH, "A")
        assert run_program(PASS_THROUGH, "A") == "\x80"

    def test_d_right_enqueues_and_d_left_dequeues(self) -> None:
        # The D on the top row enqueues the cell; the bottom D-down then
        # dequeues it, sending the pointer left to dequeue along the D row.
        run_halts(QUEUE, "A")
        assert run_program(QUEUE, "A") == ""


class TestEmptyProgram:
    def test_only_terminator_line(self) -> None:
        run_halts("DDDDDD")
        assert run_program("DDDDDD") == ""
