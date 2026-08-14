"""Unit tests for the Brainpocalypse interpreter.

Brainpocalypse is a brainfuck-like tape language: ``+``/``-`` adjust the
current cell, ``>``/``<`` move the pointer, and ``-`` on a zero cell rewinds
the instruction pointer to the start of the program.  Non-command characters
are comments.  The wiki defines no I/O; the reference reads the program from
stdin and prints the whole tape as space-separated decimals on exit, which is
what this interpreter does (there is no input command).

These tests pin the reference semantics: cells are unbounded nonnegative
integers (no 256 wrap), the tape is unbounded in both directions (no
wrap-around), and the whole used tape is printed from cell 0 regardless of
where the pointer ends up.
"""

import io
from contextlib import redirect_stdout

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.brainpocalypse import run


def run_and_capture(code: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestBrainpocalypse:
    def test_empty_program(self) -> None:
        assert run_and_capture("") == "0"

    def test_increment(self) -> None:
        assert run_and_capture("+") == "1"
        assert run_and_capture("+++") == "3"

    def test_decrement(self) -> None:
        assert run_and_capture("+-") == "0"
        assert run_and_capture("++-") == "1"
        assert run_and_capture("+++--") == "1"
        assert run_and_capture("+++---") == "0"

    def test_no_cell_wrap(self) -> None:
        """Cells are unbounded; unlike the wiki, there is no 256 wrap."""
        assert run_and_capture("+" * 300) == "300"

    def test_move_right(self) -> None:
        assert run_and_capture(">") == "0 0"
        assert run_and_capture("+>") == "1 0"
        assert run_and_capture(">+") == "0 1"
        assert run_and_capture("+>+") == "1 1"
        assert run_and_capture("++>++") == "2 2"

    def test_move_left(self) -> None:
        assert run_and_capture(">+<") == "0 1"
        assert run_and_capture("+><") == "1 0"
        assert run_and_capture("+>+<") == "1 1"
        assert run_and_capture(">+>+<<") == "0 1 1"

    def test_tape_prints_from_cell_zero(self) -> None:
        """The whole tape is printed from cell 0, wherever the pointer ends."""
        assert run_and_capture("+>") == "1 0"
        assert run_and_capture("+>+") == "1 1"
        assert run_and_capture("++>++<") == "2 2"

    def test_move_left_below_cell_zero(self) -> None:
        """The tape does not wrap; < past cell 0 just keeps moving."""
        assert run_and_capture("<") == "0"
        assert run_and_capture("<<") == "0"
        assert run_and_capture("+<") == "1"
        assert run_and_capture("+<+") == "1"

    def test_decrement_zero_rewinds(self) -> None:
        """- on a zero cell rewinds the IP instead of going negative."""
        assert run_and_capture(">>+<-") == "0 0 0 1"
        assert run_and_capture(">>++<-") == "0 0 1 2"

    def test_decrement_nonzero_continues(self) -> None:
        assert run_and_capture("++>+<-") == "1 1"
        assert run_and_capture("+++>+<-") == "2 1"
        assert run_and_capture(">+>+-") == "0 1 0"

    def test_comments_ignored(self) -> None:
        assert run_and_capture("ab+c") == "1"
        assert run_and_capture("abc+++") == "3"
        assert run_and_capture("+abc") == "1"
        assert run_and_capture(" + - > < ") == "0 0"

    def test_nul_truncates_program(self) -> None:
        """A NUL byte ends the stored program in the reference."""
        assert run_and_capture("+\x00++") == "1"

    def test_growing_programs(self) -> None:
        assert run_and_capture("+>+>+>+<<<-") == "0 1 1 1"
        assert run_and_capture("++++>+++++>++++++<<->->") == "3 4 6"
        assert run_and_capture("+++>+++>++<<--") == "1 3 2"
