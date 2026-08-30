"""Unit tests for the Brainfuck interpreter.

The interpreter pins the wrapping tape, ``<`` clamp, and bracket-matching
loop semantics directly.
"""

import importlib
import io
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.interpreters.io import IO

bf = importlib.import_module("esolangs.interpreters.tape_based.brainfuck")


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

    def test_cell_wraps_below_zero(self) -> None:
        # The upward wrap above lands on zero for any modulus, so it pins
        # neither the wrap's direction nor its width.  Decrementing from
        # zero does: it is 255 only under a modulus of exactly 256.
        assert run_and_capture("-.") == "\xff"

    def test_empty_program(self) -> None:
        assert run_and_capture("") == ""

    def test_comments_ignored(self) -> None:
        assert run_and_capture("abc+++abc.abc") == "\x03"

    def test_movement(self) -> None:
        assert run_and_capture("++>++<.>.>") == "\x02\x02"

    def test_left_clamped(self) -> None:
        """< at the left edge does nothing (the tape is clamped there)."""
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

    def test_cycle_detection_proves_an_infinite_loop(self) -> None:
        """`+[]` loops forever, decided deterministically by a state cycle."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainfuck import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine("+[]", ScriptedIO())
        assert run_until_halt_or_cycle(machine) is False

    def test_unmatched_bracket_rejected(self) -> None:
        """Unbalanced brackets are a malformed program, not a halt."""
        import pytest

        with pytest.raises(ValueError, match="unmatched"):
            run_and_capture("[")
        with pytest.raises(ValueError, match="unmatched"):
            run_and_capture("]")
        with pytest.raises(ValueError, match="unmatched"):
            run_and_capture("+]")
