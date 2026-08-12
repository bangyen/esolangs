"""Unit tests for the NoComment interpreter.

NoComment is a full wiki language: 10 commands (``i d c l r n f s b o``)
over a byte tape and a byte stack.  Non-command characters are errors (the
wiki allows no comments), as are stack underflow and jumps out of code
space.  These tests pin the plain semantics and the parity with the
transpiled brainfuck subset.
"""

import importlib
import io
from contextlib import redirect_stdout

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

nocomment = importlib.import_module("esolangs.interpreters.tape_based.nocomment")


def run_and_capture(code: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        nocomment.run(code, IO())
    return buffer.getvalue()


class TestNoComment:
    def test_output_character(self) -> None:
        assert run_and_capture("c" + "i" * 65 + "o") == "A"

    def test_cell_clears(self) -> None:
        """c resets the cell, so a following o prints a NUL."""
        assert run_and_capture("ciio") == "\x02"
        assert run_and_capture("co") == "\x00"

    def test_cell_wraps(self) -> None:
        assert run_and_capture("c" + "i" * 256 + "o") == "\x00"
        assert run_and_capture("do") == "\xff"

    def test_pointer_moves(self) -> None:
        """r extends the tape to the right; l is a no-op at cell 0."""
        assert run_and_capture("c" + "i" * 65 + "r" + "o") == "\x00"
        assert run_and_capture("c" + "i" * 65 + "r" + "i" * 70 + "o") == "F"
        assert run_and_capture("c" + "i" * 65 + "l" + "o") == "A"
        assert run_and_capture("c" + "i" * 65 + "r" + "l" + "o") == "A"

    def test_stack_push_pop(self) -> None:
        """n pushes the cell; f pops into it."""
        assert run_and_capture("c" + "i" * 65 + "n" + "f" + "o") == "A"
        assert run_and_capture("c" + "i" * 65 + "n" + "r" + "f" + "o") == "A"
        assert run_and_capture("c" + "i" * 65 + "n" + "n" + "f" + "f" + "o") == "A"

    def test_skip_forward(self) -> None:
        """s skips X commands forward when the current cell is nonzero."""
        # cell = 2, push 2: skip the two i's, print cell 2
        assert run_and_capture("cii" + "n" + "s" + "ii" + "o") == "\x02"
        assert run_and_capture("ci" + "n" + "s" + "i" + "o") == "\x01"

    def test_unrecognized_command_is_error(self) -> None:
        """The wiki allows no comments; a non-command is a malformed program."""
        with pytest.raises(ValueError, match="unrecognized NoComment command"):
            run_and_capture("x" + "c" + "i" * 65 + "o")

    def test_stack_underflow_is_error(self) -> None:
        """Popping an empty stack is an invalid operation."""
        with pytest.raises(HaltError):
            run_and_capture("c" + "i" * 65 + "f" + "o")

    def test_jump_out_of_range_is_error(self) -> None:
        """A forward or backward jump leaving the code space is invalid."""
        with pytest.raises(HaltError):
            run_and_capture("c" + "i" * 10 + "n" + "s" + "o")
        with pytest.raises(HaltError):
            run_and_capture("c" + "i" * 10 + "n" + "b" + "o")

    def test_empty_program(self) -> None:
        assert run_and_capture("") == ""

    def test_generator_round_trips(self) -> None:
        for text in ("Hello, World!", "Hi", "\x00\x01"):
            assert (
                esolangs.run("NoComment", esolangs.generate("NoComment", text)) == text
            )

    def test_parity_with_transpiled_brainfuck(self) -> None:
        """A NoComment program and its brainfuck translation agree."""
        for text in ("Hello, World!", "Hi"):
            program = esolangs.generate("NoComment", text)
            bf_program = esolangs.transpile("NoComment", "BF", program)
            assert esolangs.run("NoComment", program) == esolangs.run("BF", bf_program)
