"""Unit tests for the BF-PDA interpreter."""

import importlib
from functools import partial

import pytest

from esolangs.interpreters.io import ScriptedIO
from tests.interpreters import runner
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
)
from tests.raises import raises_message

run = importlib.import_module("esolangs.interpreters.stack_based.bf_pda").run


run_program = partial(runner.run_program, run, suppress_eof=False)


class TestOutput:
    def test_flip_and_print(self) -> None:
        assert run_program("<@.") == "1"
        assert run_program("<.") == "0"

    def test_push_and_pop(self) -> None:
        assert run_program("<<@.>.") == "10"


class TestBrackets:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            # ``[`` jumps past the body when the top bit is 0.
            pytest.param("<[.]", "", id="loop_skipped_when_top_zero"),
            # The body repeats while the top bit is 1, popping the bit out.
            pytest.param("<@[>]", "", id="loop_runs_while_top_nonzero"),
            # A ``[`` on an empty stack reads 0 and skips the body.
            pytest.param("<@[>.]", "0", id="loop_terminates_on_empty_stack"),
            # ``[`` with a zero top skips past nested ``[`` brackets.
            pytest.param("[[.]]", "", id="skip_over_nested_bracket"),
            # ``]`` with a one top jumps back across a nested ``]`` exactly once.
            pytest.param("<@<@[<@[>@]>]", "", id="jump_back_over_nested_bracket"),
        ],
    )
    def test_output(self, code: str, expected: str) -> None:
        assert run_program(code) == expected

    def test_forward_scan_skips_an_empty_inner_loop(self) -> None:
        """The forward scan counts an inner ``[`` even with nothing inside it."""
        assert run_program(".[[]@]") == "0"
        assert run_program(".[[].]") == "0"

    def test_backward_scan_lands_on_the_matching_open(self) -> None:
        """``]`` resumes at its own ``[``, counting a nested ``]`` on the way."""
        assert run_program("@<@.[>][]") == "1"
        assert run_program("@<@[>.][]") == "10"


class TestHalting:
    def test_halts_at_end_of_program(self) -> None:
        """The IP running off the end halts the machine, not a command bound."""
        assert run_program("<@." * 60) == "1" * 60


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
    def test_unmatched_brackets_rejected(self) -> None:
        with pytest.raises(ValueError, match="unmatched"):
            run_program("[")
        with pytest.raises(ValueError, match="unmatched"):
            run_program("]")
        with pytest.raises(ValueError, match="unmatched"):
            run_program("<[")
        with pytest.raises(ValueError, match="unmatched"):
            run_program("<@]")
        with pytest.raises(ValueError, match="unmatched"):
            run_program("][")
        with pytest.raises(ValueError, match="unmatched"):
            run_program("<@[.")

    def test_unmatched_open_bracket_reports_the_last_one(self) -> None:
        """The reported position is the *last* unmatched ``[``, not the first."""
        with raises_message(ValueError, "unmatched '[' at position 4"):
            run_program("<[.<[.")

    def test_an_unmatched_open_is_named_even_when_a_later_one_matched(self) -> None:
        """The position names an *unmatched* ``[``, not the last one written."""
        with raises_message(ValueError, "unmatched '[' at position 0"):
            run_program("[[]")

    def test_unmatched_close_bracket_reports_its_own_position(self) -> None:
        """A stray ``]`` names the index it sits at, checked exactly."""
        with raises_message(ValueError, "unmatched ']' at position 2"):
            run_program("<@]")


class TestStepMachine:
    def test_snapshot_changes_after_a_step(self) -> None:
        from esolangs.interpreters.stack_based.bf_pda import _Machine

        machine = _Machine("<", ScriptedIO())
        before = machine.snapshot()
        machine.step()  # < pushes a zero
        assert machine.snapshot() != before
        assert machine.stack == (0,)


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.bf_pda import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, CycleContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
    machine = staticmethod(_machine)
    empty_raises = "BF-PDA program cannot be empty"
    halting_program = "<@."
    looping_program = "<@[@@]"
