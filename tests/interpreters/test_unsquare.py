"""Unit tests for the Unsquare interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.unsquare import run


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class TestUnsquare:
    def test_push_and_print(self) -> None:
        assert run_program("Io") == "\x01"
        assert run_program("Oo") == "\x00"

    def test_print_does_not_pop(self) -> None:
        assert run_program("Ooo") == "\x00\x00"

    def test_accumulator_ops(self) -> None:
        assert run_program("I+Po") == "\x02"
        assert run_program("++Po") == "\x04"
        assert run_program("-Po") == "-2"  # -2 is not a valid code point
        assert run_program("xxPo") == "\x00"

    def test_swap(self) -> None:
        assert run_program("OISo") == "\x00"

    def test_read_input(self) -> None:
        assert run_program("iPo", "7\n") == "\x00"

    def test_read_pushes_first_char(self) -> None:
        assert run_program("iPo", "hi\n") == "\x00"  # acc is 0, P pushes it

    def test_read_blank_lines_reprompt(self) -> None:
        assert run_program("iPo", "\n\n7\n") == "\x00"

    def test_print_letter(self) -> None:
        assert run_program("+" * 32 + "Po") == "@"

    def test_loop_skips_when_acc_01(self) -> None:
        assert run_program("O>I<") == ""
        assert run_program("I>I<") == ""

    def test_loop_counts_down(self) -> None:
        # acc 4: each pass pushes acc, prints, and subtracts 2; the > records
        # and re-checks until acc reaches 0, then skips past the <.
        assert run_program("++>Po-<") == "\x04\x02"

    def test_error_empty_stack(self) -> None:
        with pytest.raises(HaltError):
            run_program("A")
        with pytest.raises(HaltError):
            run_program("o")
        with pytest.raises(HaltError):
            run_program("S")

    def test_error_unmatched_brackets(self) -> None:
        with pytest.raises(HaltError):
            run_program("<")
        with pytest.raises(HaltError):
            run_program(">")

    def test_empty_program(self) -> None:
        assert run_program("") == ""
