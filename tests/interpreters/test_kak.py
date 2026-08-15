"""Unit tests for the Kak interpreter."""

import importlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO

run = importlib.import_module("esolangs.interpreters.tape_based.kak").run


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class TestKak:
    def test_empty_program(self) -> None:
        """The empty program always runs one pass and prints the initial tape."""
        assert run_program("") == "0\n"

    def test_advance_and_flip(self) -> None:
        """A ! advances and flips; the < returns to the zero cell and halts."""
        assert run_program("!<") == "01\n"

    def test_restart_while_nonzero(self) -> None:
        """Passes repeat until the current bit is zero, printing the tape."""
        assert run_program("!!<") == "011\n0101\n"

    def test_multi_pass_restart(self) -> None:
        """A wider left retrace produces a second pass that clears the tape."""
        assert run_program("!!!<<") == "0111\n01001\n"

    def test_question_mark_consumes_special_char(self) -> None:
        """A zero-bit ? skips the next special char (consumed, not executed)."""
        assert run_program("?!a") == "0\n"
        assert run_program("?<") == "0\n"

    def test_question_mark_skips_nops_to_special(self) -> None:
        """The skip consumes nops and stops at (and consumes) a special char."""
        assert run_program("?a!") == "0\n"
        assert run_program("?ab?cd") == "0\n"

    def test_question_mark_on_nonzero_is_noop(self) -> None:
        """A ? with the current bit set does nothing and the < halts."""
        assert run_program("!?<") == "01\n"

    def test_unknown_chars_are_nops(self) -> None:
        """Characters other than !?< do not change execution."""
        assert run_program("!< abc xyz \n") == "01\n"

    def test_later_pass_skip(self) -> None:
        """A ? that is a no-op on pass one skips on a later pass and halts."""
        assert run_program("!!!<?<!<") == "0101\n01100\n"

    def test_question_mark_at_end_is_not_an_error(self) -> None:
        """A ? with nothing after it stops the skip without error (the
        cross-check's failed get leaves the '?' itself in the buffer)."""
        assert run_program("?") == "0\n"
        assert run_program("!<?") == "01\n"
        assert run_program("!!<?") == "011\n0101\n"

    def test_question_mark_off_end_halts(self) -> None:
        """A ? that runs off the program while skipping halts (no output)."""
        with pytest.raises(HaltError):
            run_program("!<?a")

    def test_question_mark_off_end_after_nops_halts(self) -> None:
        """Skipping through nops to the end of the program also halts."""
        with pytest.raises(HaltError):
            run_program("a?b")

    def test_later_pass_off_end_halts(self) -> None:
        """An off-end ? on a later pass halts after printing that pass's tape."""
        io = ScriptedIO("")
        with pytest.raises(HaltError):
            run("!!< ?x", io)
        assert io.getvalue() == "011\n"
