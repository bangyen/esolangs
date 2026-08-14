"""Unit tests for the BF-PDA interpreter.

BF-PDA is a brainfuck variant over a stack of bits whose top is the current
cell; the semantics (including the bracket behavior and the 100-command run
bound) port the Lean reference binary exactly.  These tests pin the valid
programs to the reference outputs and the error handling to the repo
conventions (``HaltError`` for invalid operations, ``ValueError`` for a
malformed program).
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
    def test_body_runs_once_when_top_zero(self) -> None:
        """A matched pair enters and leaves the body once (no brainfuck loop)."""
        assert run_program("<[.]") == "0"

    def test_body_runs_once_when_top_one(self) -> None:
        assert run_program("<@[.]") == "1"

    def test_loop_flip_prints_both_bits(self) -> None:
        assert run_program("<@[.@.]") == "10"

    def test_loop_push_print_pop(self) -> None:
        assert run_program("<@[<@>.]") == "1"

    def test_nested_loops(self) -> None:
        assert run_program("<@[[.]]") == "1"
        assert run_program("<@[[.].]") == "11"

    def test_nested_scan_from_zero_top(self) -> None:
        """A ``[`` with a zero top scans across a nested ``[`` for its match."""
        assert run_program("<[[.]]") == "0"

    def test_inner_loop_with_push(self) -> None:
        assert run_program("<[<@.]") == "1"
        assert run_program("<[<@.>]") == "1"

    def test_complex_loops(self) -> None:
        assert run_program("<.@[.]") == "01"
        assert run_program("<.@[<@[.].@.>].@.>") == "011010"


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
    def test_pop_empty_stack_halts(self) -> None:
        with pytest.raises(HaltError, match="pop an empty stack"):
            run_program(">")
        with pytest.raises(HaltError, match="pop an empty stack"):
            run_program(">>")
        with pytest.raises(HaltError, match="pop an empty stack"):
            run_program("<>>")

    def test_top_access_on_empty_stack_halts(self) -> None:
        with pytest.raises(HaltError, match="top bit"):
            run_program(".")
        with pytest.raises(HaltError, match="top bit"):
            run_program("@")
        with pytest.raises(HaltError, match="top bit"):
            run_program("[<@.>]")
        with pytest.raises(HaltError, match="top bit"):
            run_program("<[>]")
        with pytest.raises(HaltError, match="top bit"):
            run_program("<@>.")


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
