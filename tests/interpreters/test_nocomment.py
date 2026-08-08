"""Unit tests for the NoComment interpreter.

NoComment is a strict subset of brainfuck (``c`` clear, ``i`` increment,
``o`` output; everything else is a comment), so the interesting property is
that a program and its brainfuck translation behave identically.  These
tests also pin the plain semantics directly.
"""

import importlib
import io
from contextlib import redirect_stdout

import esolangs

nocomment = importlib.import_module("esolangs.interpreters.tape_based.nocomment")


def run_and_capture(code: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        nocomment.run(code)
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

    def test_comments_ignored(self) -> None:
        program = "xyz " + "c" + "i" * 65 + "o" + " qwerty"
        assert run_and_capture(program) == "A"

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
