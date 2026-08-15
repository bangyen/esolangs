"""Unit tests for the BF-PDA interpreter.

BF-PDA is a brainfuck variant over a stack of bits whose top is the current
cell.  Per the wiki: ``[``/``]`` are while loops, and an empty stack behaves
as a zero (``>`` pops nothing, ``@``/``.``/``[`` read 0).  A run is bounded
at ``limit`` commands so loops that never empty the stack terminate.
"""

import importlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO

run = importlib.import_module("esolangs.interpreters.tape_based.bfpda").run


def run_program(code: str, limit: int = 100) -> str:
    io = ScriptedIO()
    run(code, io, limit=limit)
    return io.getvalue()


class TestOutput:
    def test_flip_and_print(self) -> None:
        assert run_program("<@.") == "1"
        assert run_program("<.") == "0"

    def test_flip_wraps_to_zero_and_back(self) -> None:
        assert run_program("<@@.") == "0"
        assert run_program("<@@@.") == "1"

    def test_push_and_pop(self) -> None:
        assert run_program("<<@.>.") == "10"

    def test_comments_ignored(self) -> None:
        assert run_program("abc<@.xyz") == "1"

    def test_newlines_ignored(self) -> None:
        assert run_program("<@\n.\t>") == "1"


class TestBrackets:
    def test_loop_skipped_when_top_zero(self) -> None:
        """``[`` jumps past the body when the top bit is 0."""
        assert run_program("<[.]") == ""

    def test_loop_runs_while_top_nonzero(self) -> None:
        """The body repeats while the top bit is 1, popping the bit out."""
        assert run_program("<@[>]") == ""

    def test_loop_prints_each_bit(self) -> None:
        assert run_program("<@<@[.>]") == "11"

    def test_loop_flips_to_zero_and_exits(self) -> None:
        assert run_program("<@[@.]") == "0"

    def test_loop_terminates_on_empty_stack(self) -> None:
        """A ``[`` on an empty stack reads 0 and skips the body."""
        assert run_program("<@[>.]") == "0"

    def test_nested_loops(self) -> None:
        assert run_program("<@<@[>[@]]") == ""
        assert run_program("<@<@[>[>].]") == "0"

    def test_loop_does_not_run_past_limit(self) -> None:
        """A loop that never empties the stack stops at the command bound."""
        assert run_program("<@[.]", limit=6) == "1"


class TestLimit:
    def test_default_limit_matches_reference(self) -> None:
        """The reference runs at most 100 commands; 33 of the 60 triples run."""
        assert run_program("<@." * 60) == "1" * 33

    def test_override_limit(self) -> None:
        assert run_program("<@." * 60, limit=200) == "1" * 60

    def test_long_program_truncated(self) -> None:
        assert run_program("<" * 110 + ".") == ""
        assert run_program("<" * 50 + "." * 10 + "<" * 200) == "0" * 10


class TestEmptyStack:
    def test_pop_empty_stack_is_noop(self) -> None:
        """Popping an empty stack does nothing rather than halting."""
        assert run_program(">") == ""
        assert run_program(">>") == ""
        assert run_program("<>>") == ""

    def test_top_access_on_empty_stack_reads_zero(self) -> None:
        """Peeking an empty stack reads 0; ``@`` pushes and flips it."""
        assert run_program(".") == "0"
        assert run_program("@.") == "1"
        assert run_program("[<@.>]") == ""
        assert run_program("<@>.") == "0"


class TestMalformed:
    def test_empty_program_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            run_program("")

    def test_unmatched_brackets_halt(self) -> None:
        with pytest.raises(HaltError, match="unmatched"):
            run_program("[")
        with pytest.raises(HaltError, match="unmatched"):
            run_program("]")
        with pytest.raises(HaltError, match="unmatched"):
            run_program("<[")
        with pytest.raises(HaltError, match="unmatched"):
            run_program("<@]")
        with pytest.raises(HaltError, match="unmatched"):
            run_program("][")
        with pytest.raises(HaltError, match="unmatched"):
            run_program("<@[.")
