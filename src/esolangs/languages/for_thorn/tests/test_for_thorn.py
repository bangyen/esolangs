"""Unit tests for the Forþ interpreter."""

from functools import partial

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.for_thorn.interpreter import _advance, _Machine, run
from esolangs.languages.for_thorn.interpreter import _Machine as Forth
from esolangs.languages.for_thorn.tests.oracle_checks import check_raw_for_thorn
from esolangs.runtime._result_wire import _state_from_wire, _state_wire
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import run_until_halt_or_ancestor, run_until_halt_or_cycle
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    InputCursorContract,
    machine_factory,
    reader_factory,
)
from tests.interpreters.cursorless_io import PositionlessIO
from tests.interpreters.runner import run_program as _run_program
from tests.support.execution import termination_observed

run_program = partial(_run_program, run, suppress_eof=False)


class TestStepMachine:
    def test_arithmetic_wraps_to_a_signed_32_bit_range(self) -> None:
        """Results wrap into -2**31 .. 2**31-1, which only the stack shows."""
        machine = _Machine("9:*:*:*:*", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert list(machine.stack) == [-501334399]

    def test_step_tracks_stack_and_active_frame_cursor(self) -> None:
        check_raw_for_thorn()
        machine = _Machine("65.", ScriptedIO())
        assert (list(machine.stack), machine.frames[0].pc) == ([], 0)
        machine.step()  # 6 pushes
        assert (list(machine.stack), machine.frames[0].pc) == ([6], 1)
        machine.step()  # 5 pushes
        assert list(machine.stack) == [6, 5]
        machine.step()  # . pops and prints the low byte
        assert machine.io.getvalue() == "\x05"
        machine.step()  # finalizing the finished frame halts the machine
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert list(machine.frames) == []

    def test_nested_scope_pushes_a_frame_and_aborts_discard_the_error(
        self, monkeypatch
    ) -> None:
        machine = _Machine("1{/}1;", ScriptedIO())
        for _ in range(4):  # 1 {/} 1 ; -> the ; pushes the "/" scope
            machine.step()
        assert len(machine.frames) == 2
        machine.step()  # the "/" underflow aborts the scope (and ends the run)
        assert machine.halted
        assert machine.error is False  # the nested error is discarded

        # A closer in the caller cannot close a bracket in the stored body.
        assert run_program("1{(};)2.") == "\x02"

        from esolangs.languages.for_thorn import interpreter
        from tests.support.prepared_support import check_image_reuse

        check_image_reuse(
            "Forþ", ",1{(.)};", interpreter, "_prepare_source", monkeypatch
        )

    def test_a_top_level_abort_raises_from_step(self) -> None:
        """A stepped run fails as ``run`` does, not as a quiet halt."""
        machine = _Machine("0/", ScriptedIO())
        machine.step()
        with pytest.raises(HaltError, match="top-level scope aborted"):
            machine.step()

        machine = _Machine("(2)", ScriptedIO())
        with pytest.raises(HaltError, match="stack is empty"):
            machine.step()
        assert machine.ip == (3,)

    def test_the_wrap_folds_at_exactly_two_to_the_thirty_first(self) -> None:
        """2**31 is the first value that wraps, and it lands on the floor."""
        machine = _Machine("2:*:*:*:*88*8*8*8**", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert list(machine.stack) == [-2147483648]

    def test_the_read_pushes_every_byte_of_the_line(self) -> None:
        """``,`` pushes the whole line, one byte per cell."""
        machine = _Machine(",", ScriptedIO("hi"))
        machine.step()
        assert list(machine.stack) == [104, 105]

    def test_a_loop_reenters_its_frame_each_pass(self) -> None:
        """A loop restarts its body until the top reaches zero."""
        machine = _Machine("3[:1-]", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert list(machine.stack) == [3, 2, 1, 0]

    def test_an_unstored_key_calls_an_empty_scope(self) -> None:
        """``;`` falls back to the empty string, so the pushed frame has code."""
        machine = _Machine("1;", ScriptedIO())
        machine.step()  # 1 pushes the key
        machine.step()  # ; pops it and pushes the stored scope
        assert [frame.code for frame in machine.frames] == ["1;", ""]


def test_a_read_loop_on_a_cursorless_port_is_not_a_cycle() -> None:
    """A port with no cursor reports position 0; the snapshot counts reads."""
    with pytest.raises(EOFError):
        run_until_halt_or_cycle(_Machine("1[,]", PositionlessIO("\n" * 10)), limit=100)
    _check_proof_read_failure()


def _check_proof_read_failure() -> None:
    from esolangs.exceptions import InputExhaustedError
    from esolangs.results import ExecutionResult
    from esolangs.runtime._isolated import termination_result_isolated

    with pytest.raises(InputExhaustedError) as local:
        termination_observed("Forþ", ",.,", "A", 5)
    with pytest.raises(InputExhaustedError) as worker:
        termination_result_isolated("Forþ", ",.,", "A", 5)
    assert local.value.partial_output == worker.value.partial_output == "A"
    assert (
        local.value.execution == worker.value.execution == ExecutionResult("A", 1, 1, 1)
    )


class TestContract(EmptyProgramContract, CycleContract, InputCursorContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
    machine = staticmethod(machine_factory(_Machine, ScriptedIO))
    reader = staticmethod(reader_factory(_Machine, ScriptedIO))
    reading_program = ","
    reading_stdin = "hi"
    position_after_read = 2
    halting_program = "65."
    looping_program = "1[]"


def test_forth_replayed_scope_is_detected_as_an_ancestor() -> None:
    # Store 1; under key 1, then have that scope call itself forever.
    machine = Forth("1{1;}1;", ScriptedIO())
    assert run_until_halt_or_ancestor(machine) is False


def test_forth_changing_stack_halts() -> None:
    # The scope decrements its shared counter before conditionally
    # calling itself, so every entered scope has a different binding.
    machine = Forth("1{1-(1;)}3v;", ScriptedIO())
    assert run_until_halt_or_ancestor(machine) is True


def test_scope_transition_keeps_old_tables_immutable() -> None:
    machine = Forth("1{2}", ScriptedIO(""))
    machine.step()
    before = machine._state
    moved = _advance(before)
    assert before[1] == {}
    assert moved[1] == {1: "2"}
    with pytest.raises(TypeError):
        moved[1][1] = "3"
    assert _advance(before) == moved


def test_workspace_scope_values_survive_backing_root_moves():
    machine = Forth("1{a}2{b}1{x}", ScriptedIO())
    machine.step()
    machine.step()
    first_table = machine.table
    saved = machine.workspace_snapshot()
    restored = _state_from_wire(_state_wire(first_table))
    assert restored == first_table
    assert hash(restored) == hash(first_table)
    for payload in ((), frozenset({(1, "a"), (1, "b")}), frozenset({(True, "a")})):
        packet = _state_wire(first_table)
        packet["owned"]["value"] = _state_wire(payload)
        with pytest.raises(ValueError, match="snapshot"):
            _state_from_wire(packet)
    retained = {saved}
    for _ in range(4):
        machine.step()
        assert dict(first_table.items()) == {1: "a"}
        assert saved in retained
        assert restored == first_table
        assert hash(restored) == hash(first_table)
    assert dict(machine.table.items()) == {1: "x", 2: "b"}
    assert machine.workspace_snapshot().parts[1] == frozenset({(1, "x"), (2, "b")})
    assert saved.parts[1] == frozenset({(1, "a")})
    assert machine.table.delta(first_table) == ([(2, "b"), (1, "x")], [(1, "a")])
