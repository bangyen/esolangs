"""Tests for the Bitwise Cyclic Tag interpreter."""

import pytest

from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.queue_based.bitwise_cyclic_tag import _Machine, run
from tests.interpreters.contract import (
    CycleContract,
    SnapshotContract,
    StateViewContract,
)
from tests.interpreters.runner import run_program

#: The wiki's example: program ``00111`` on data ``101``, as
#: ``(command, data-string before it)`` pairs, read off the published table.
#: The system never halts, so the trace is a prefix and the test steps
#: exactly as far as it goes.
_WIKI_TRACE = [
    ("0", "101"),
    ("0", "01"),
    ("11", "1"),
    ("10", "11"),
    ("0", "110"),
    ("11", "10"),
    ("10", "101"),
    ("0", "1010"),
    ("11", "010"),
    ("10", "010"),
    ("0", "010"),
    ("11", "10"),
]


class TestTheWikiExample:
    def test_the_published_trace_is_reproduced(self) -> None:
        """Every data-string in the wiki's table, in order."""
        machine = _Machine("00111,101", ScriptedIO())
        for command, data in _WIKI_TRACE:
            assert machine.live == data, (command, data)
            machine.step()

    def test_the_command_sequence_is_the_published_cycle(self) -> None:
        """``0 (0 11 10)(0 11 10)...``, which is where the operand wraps."""
        machine = _Machine("00111,101", ScriptedIO())
        heads = []
        for _ in _WIKI_TRACE:
            heads.append(machine.head)
            machine.step()
        assert heads == [0, 1, 2, 4, 1, 2, 4, 1, 2, 4, 1, 2]


class TestBitwiseCyclicTag:
    def test_a_lone_delete_answers_the_bit_it_took(self) -> None:
        assert run_program(run, "0,1") == "1"
        assert run_program(run, "0,0") == "0"

    def test_the_answer_is_the_last_deletion_not_the_first(self) -> None:
        """Two deletions, and the second one is what is reported."""
        assert run_program(run, "00,10") == "0"
        assert run_program(run, "00,01") == "1"

    def test_a_one_appends_its_operand_only_on_a_one(self) -> None:
        """``10`` after a ``1`` extends the data, so a third bit is deleted."""
        assert run_program(run, "1000,11") == "0"  # the appended 0 is last out
        assert run_program(run, "1000,01") == "1"  # no append, so 1 is last out

    def test_an_empty_data_string_halts_with_no_answer(self) -> None:
        """The wiki's first sentence, and nothing was ever deleted."""
        assert run_program(run, "0011,") == ""
        assert run_program(run, "0011") == ""

    def test_a_second_comma_is_refused(self) -> None:
        with pytest.raises(ValueError, match="one ',' at most"):
            run_program(run, "0,1,1")

    def test_a_non_bit_is_refused(self) -> None:
        with pytest.raises(ValueError, match="not a Bitwise Cyclic Tag bit"):
            run_program(run, "0012,1")

    def test_the_answer_prints_once_however_far_it_is_stepped(self) -> None:
        """The post-halt step prints it, and only the first one does."""
        io_obj = ScriptedIO()
        machine = _Machine("0,1", io_obj)
        while not machine.halted:
            machine.step()
        assert io_obj.getvalue() == ""  # nothing until the step past the halt
        machine.step()
        assert io_obj.getvalue() == "1"
        for _ in range(3):
            machine.step()
        assert io_obj.getvalue() == "1"

    def test_a_deleted_prefix_is_not_part_of_the_state(self) -> None:
        """Two runs that differ only in what they have already deleted agree."""
        early = _Machine("11,0", ScriptedIO())
        late = _Machine("011,10", ScriptedIO())
        late.step()  # delete the leading 1, leaving the same live data
        assert early.live == late.live == "0"
        assert early.snapshot()[2] == late.snapshot()[2]


def _machine(code: object) -> object:
    return _Machine(code, IO())


class TestContract(SnapshotContract, CycleContract, StateViewContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "00,11"
    halting_program = "0,1"
    # A genuine snapshot revisit, which is narrower here than "does not
    # halt": the read cursor only ever advances, so any program that deletes
    # a bit reaches a state it has never been in.  ``11`` on a leading 0
    # appends nothing and returns the pointer to where it started, so
    # nothing at all changes -- the one shape that repeats.
    looping_program = "11,0"
    state_views = ("ip", "memory", "head", "read", "answer", "live")
    viewing_program = "00,11"
