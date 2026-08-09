"""Unit tests for the Brainfuck interpreter.

The interpreter is defined to be interchangeable with the ASCII-art
interpreter (same wrapping tape, ``<`` clamp, and bracket-matching loops),
so the interesting property here is parity: any brainfuck program must
behave identically when its ASCII-art translation runs instead.  These
tests also pin the plain semantics directly.
"""

import importlib
import io
from contextlib import redirect_stdout
from unittest.mock import patch

import esolangs
from esolangs.interpreters.io import IO

bf = importlib.import_module("esolangs.interpreters.tape_based.bf")


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        bf.run(code, IO())
    return buffer.getvalue()


class TestBrainfuck:
    def test_output_character(self) -> None:
        assert run_and_capture("+" * 65 + ".") == "A"

    def test_cell_wraps(self) -> None:
        assert run_and_capture("+" * 256 + ".") == "\x00"

    def test_empty_program(self) -> None:
        assert run_and_capture("") == ""

    def test_comments_ignored(self) -> None:
        assert run_and_capture("abc+++abc.abc") == "\x03"

    def test_movement(self) -> None:
        assert run_and_capture("++>++<.>.>") == "\x02\x02"

    def test_left_clamped(self) -> None:
        """< at the left edge does nothing (matches ASCII-art semantics)."""
        assert run_and_capture("<<.") == "\x00"

    def test_input_echo(self) -> None:
        assert run_and_capture(",>,<.>.", inputs=["A", "B"]) == "AB"

    def test_loop_zeroing(self) -> None:
        """+[-] enters a loop, zeroes the cell, and exits."""
        assert run_and_capture("+[-].") == "\x00"

    def test_loop_skipped_when_zero(self) -> None:
        assert run_and_capture("[.]") == ""

    def test_loop_iterates_while_nonzero(self) -> None:
        """++[>+<-] moves 2 from cell 0 to cell 1."""
        assert run_and_capture("++[>+<-]>.>.") == "\x02\x00"

    def test_nested_loop(self) -> None:
        """A doubly-nested loop leaves a known value in the printed cell."""
        assert run_and_capture("+++[>++[>+<-]<-]>+++.") == "\x03"

    def test_unmatched_bracket_rejected(self) -> None:
        """Unbalanced brackets are a malformed program, not a halt."""
        import pytest

        with pytest.raises(ValueError, match="unmatched"):
            run_and_capture("[")
        with pytest.raises(ValueError, match="unmatched"):
            run_and_capture("]")
        with pytest.raises(ValueError, match="unmatched"):
            run_and_capture("+]")

    def test_parity_with_ascii_art(self) -> None:
        """A program and its ASCII-art translation behave identically."""
        programs = [
            "+++[>++[>+<-]<-]>+++.",
            "+++[>++<-]>++.>",
            ">+<<.",
        ]
        for program in programs:
            art = esolangs.transpile("BF", "ASCII art", program)
            assert esolangs.run("BF", program) == esolangs.run("ASCII art", art)
