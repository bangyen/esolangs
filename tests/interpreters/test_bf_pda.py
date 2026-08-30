"""Unit tests for the BF-PDA interpreter.

BF-PDA is a brainfuck variant over a stack of bits whose top is the current
cell.  Per the wiki: ``[``/``]`` are while loops, an empty stack behaves as a
zero (``>`` pops nothing, ``@``/``.``/``[`` read 0), and a run halts when the
instruction pointer reaches the end of the program.
"""

import importlib

import pytest

from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.contract import EmptyProgramContract

run = importlib.import_module("esolangs.interpreters.stack_based.bf_pda").run


def run_program(code: str) -> str:
    io = ScriptedIO()
    run(code, io)
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

    def test_skip_over_nested_bracket(self) -> None:
        """``[`` with a zero top skips past nested ``[`` brackets."""
        assert run_program("[[.]]") == ""

    def test_jump_back_over_nested_bracket(self) -> None:
        """``]`` with a one top jumps back across a nested ``]`` exactly once."""
        assert run_program("<@<@[<@[>@]>]") == ""


class TestHalting:
    def test_halts_at_end_of_program(self) -> None:
        """The IP running off the end halts the machine, not a command bound."""
        assert run_program("<@." * 60) == "1" * 60

    def test_long_program_not_truncated(self) -> None:
        assert run_program("<" * 110 + ".") == "0"
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


class TestStepMachine:
    def test_snapshot_changes_after_a_step(self) -> None:
        from esolangs.interpreters.stack_based.bf_pda import _Machine

        machine = _Machine("<", ScriptedIO())
        before = machine.snapshot()
        machine.step()  # < pushes a zero
        assert machine.snapshot() != before
        assert machine.stack == [0]

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.stack_based.bf_pda import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("<@.", ScriptedIO())) is True

    def test_loop_is_detected_as_a_cycle(self) -> None:
        # <@[@@] pushes a 1, then loops flipping the top bit twice each pass
        # (a no-op), so ] always sees a 1 and jumps back forever.
        from esolangs.interpreters.stack_based.bf_pda import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("<@[@@]", ScriptedIO())) is False

    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.stack_based.bf_pda import _Machine

        machine = _Machine("<", ScriptedIO())
        machine.step()  # < pushes a zero
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.stack == [0]


class TestContract(EmptyProgramContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
    empty_raises = "BF-PDA program cannot be empty"
