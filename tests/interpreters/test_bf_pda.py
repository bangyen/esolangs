"""Unit tests for the BF-PDA interpreter.

BF-PDA is a brainfuck variant over a stack of bits whose top is the current
cell.  Per the wiki: ``[``/``]`` are while loops, an empty stack behaves as a
zero (``>`` pops nothing, ``@``/``.``/``[`` read 0), and a run halts when the
instruction pointer reaches the end of the program.
"""

import importlib

import pytest

from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
)

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

    def test_forward_scan_skips_an_empty_inner_loop(self) -> None:
        """The forward scan counts an inner ``[`` even with nothing inside it.

        Every nested case here puts commands between the inner brackets, so
        a scan that miscounts still lands on a command and prints the same
        thing.  An *empty* inner loop is the tight case: in ``[[]@]`` the
        skip from the outer ``[`` has to pass ``[]`` and stop after the
        outer ``]``.  A scan that starts one character further along, or
        that never raises its depth on an inner ``[``, stops at the inner
        ``]`` instead and resumes inside the loop.

        The leading ``.`` prints the empty stack's zero, and the outer
        ``[`` reads that same zero and skips -- so the program prints once
        and halts, where a mis-landed scan runs ``@`` and prints again.
        """
        assert run_program(".[[]@]") == "0"
        assert run_program(".[[].]") == "0"

    def test_backward_scan_lands_on_the_matching_open(self) -> None:
        """``]`` resumes at its own ``[``, counting a nested ``]`` on the way.

        The jump-back tests all sit next to a command, so a scan returning
        one index either side still lands on something equivalent.  Here
        the outer ``]`` is preceded directly by an inner ``][``, so the
        index it computes is the difference between resuming at the outer
        ``[`` and resuming one cell off it.
        """
        assert run_program("@<@.[>][]") == "1"
        assert run_program("@<@[>.][]") == "10"


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

    def test_unmatched_open_bracket_reports_the_last_one(self) -> None:
        """The reported position is the *last* unmatched ``[``, not the first.

        ``match=`` is a substring search, so every case above passes on any
        position at all -- the number was never asserted.  With two
        unmatched brackets the choice becomes visible: this program opens
        at 1 and again at 4, and the message names 4.  Reporting the first
        would say 1, and a search that finds nothing would say -1.
        """
        with pytest.raises(ValueError) as caught:
            run_program("<[.<[.")
        assert str(caught.value) == "unmatched '[' at position 4"

    def test_unmatched_close_bracket_reports_its_own_position(self) -> None:
        """A stray ``]`` names the index it sits at, checked exactly."""
        with pytest.raises(ValueError) as caught:
            run_program("<@]")
        assert str(caught.value) == "unmatched ']' at position 2"


class TestStepMachine:
    def test_snapshot_changes_after_a_step(self) -> None:
        from esolangs.interpreters.stack_based.bf_pda import _Machine

        machine = _Machine("<", ScriptedIO())
        before = machine.snapshot()
        machine.step()  # < pushes a zero
        assert machine.snapshot() != before
        assert machine.stack == [0]

    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.stack_based.bf_pda import _Machine

        machine = _Machine("<", ScriptedIO())
        machine.step()  # < pushes a zero
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.stack == [0]


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
