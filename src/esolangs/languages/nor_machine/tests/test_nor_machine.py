"""Tests for the NOR machine interpreter."""

import pytest

from esolangs import ExecutionLimits, ExecutionResult, HaltError, Language
from esolangs.languages.nor_machine.interpreter import _Machine, run
from esolangs.runtime._state import WorkspaceVariant
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import _capture_workspace
from tests.interpreters.runner import native_runner
from tests.support.vm_support import assert_rejected_input_retry


@pytest.mark.medium
def test_rejected_input_stays_with_the_failed_step() -> None:
    assert_rejected_input_retry(
        "NOR machine", "V", "x", "7", "7", position=1, reads=1, rejected="x"
    )


_out = native_runner(run)


def test_lone_nor_prints_the_value_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _out("V", "5") == "5"
    api = Language("NOR machine")
    limits = ExecutionLimits(max_steps=1)
    complete = api.run("V", stdin="123", limits=limits)
    assert (complete.output, complete.steps) == ("123", 1)
    write = ScriptedIO._write

    def check(accepted: int) -> None:
        attempts: list[object] = []
        fault = HaltError("transient output refusal")

        def refuse(io: ScriptedIO, value: object) -> None:
            attempts.append(value)
            if len(attempts) == 1:
                write(io, "123"[:accepted])
                raise fault
            write(io, value)

        with monkeypatch.context() as port:
            port.setattr(ScriptedIO, "_write", refuse)
            debug = api.make_debugger("V", stdin="123")
            with pytest.raises(HaltError, match="output refusal") as caught:
                debug.run(limits=limits)
            assert caught.value is fault
            partial = ExecutionResult("123"[:accepted], 3, 1, 0, steps=0)
            assert debug.observation == fault.observation == partial
            assert not debug.halted
            state = (0, (123,), False, 3)
            assert debug.snapshot() == ((*state, accepted) if accepted else state)
            assert _capture_workspace(debug.vm).parts[2] == (
                WorkspaceVariant("pending_output", (False, accepted))
                if accepted
                else False
            )
            assert debug.run(limits=limits) == "halted"
            assert debug.observation == complete
            assert fault.observation == partial
        assert type(attempts[0]) is int
        assert attempts == [123] + (
            ["123"[accepted:] if accepted else 123] if accepted < 3 else []
        )

    for accepted in range(4):
        check(accepted)


@pytest.mark.parametrize("part", [0, 1])
def test_nor_is_twos_complement(part) -> None:
    from esolangs.languages.nor_machine.tests.oracle_checks import (
        check_raw_nor_machine,
    )

    check_raw_nor_machine(part)
    # ~(5 | 2) = -8.
    assert _out("V V", "5 2") == "-8"


def test_shifts_floor_on_negatives() -> None:
    assert _out("R V", "-1") == "-1"
    assert _out("L V", "-3") == "-6"


def test_swap_and_rotate_reorder_the_queue() -> None:
    # 4 3 -> X -> 3 4 -> L -> 4 6 -> R -> 6 2 -> V prints ~(6 | 2) = -7.
    assert _out("XLRVV", "4 3") == "-7"
    # 8 1 -> I -> 1 8 -> R -> 8 0 -> V prints ~(8 | 0) = -9.
    assert _out("IRVV", "8 1") == "-9"


def test_dup_enqueues_twice() -> None:
    # 3 -> 3 3 -> ~(3 | 3) = -4.
    assert _out("AVV", "3") == "-4"


def test_program_repeats_until_a_lone_nor() -> None:
    # L doubles the value each pass, then V ends the first pass on one value.
    assert _out("L V", "1") == "2"
    io = ScriptedIO("1 2")
    machine = _Machine("L", io)
    for _ in range(50):
        machine.step()
    assert not machine.halted


def test_whitespace_is_skipped_and_bad_source_is_rejected(monkeypatch) -> None:
    assert _out(" L\n V ", "3") == "6"
    with pytest.raises(ValueError, match="unknown command"):
        _out("Lx", "1")
    with pytest.raises(ValueError, match="no command"):
        _out(" ")

    from esolangs.languages.nor_machine import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "NOR machine",
        " L V ",
        interpreter,
        "_parse",
        monkeypatch,
        cases=(("1", "2"), ("3", "6"), ("-1", "-2")),
    )
