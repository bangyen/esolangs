"""Unit tests for RAM0 interpreter."""

import sys
from dataclasses import replace

import pytest

from esolangs import ExecutionLimits, ExecutionResult, Language
from esolangs.exceptions import HaltError
from esolangs.languages.ram0.interpreter import _Machine, run
from esolangs.runtime._lifecycle import POST_HALT_REPORT
from esolangs.runtime._state import WorkspaceVariant
from esolangs.runtime.io import IO, ScriptedIO
from esolangs.vm import _capture_workspace
from tests.interpreters.contract import (
    CycleContract,
    SnapshotContract,
    StateViewContract,
)
from tests.interpreters.runner import run_printing


def dump(code: str) -> str:
    """Run ``code`` and return the state dump it prints."""
    return run_printing(run, code)


_DUMPS = {
    # Increment z to 3, then zero it
    "z_command_zero_register": ("A A A Z", "z: 0\nn: 0\nram: {}"),
    # z=3, then copy to n
    "n_command_copy_z_to_n": ("A A A N", "z: 3\nn: 3\nram: {}"),
    # Store 5 at address 2, then L loads from uninitialized address 7: 0
    "l_command_load_from_memory": (
        "A A N A A A S A A L",
        "z: 0\nn: 2\nram: {\n    2: 5\n}",
    ),
    "s_command_store_to_memory": ("A A N A A A S", "z: 5\nn: 2\nram: {\n    2: 5\n}"),
    # Skip A if z is zero (it is)
    "c_command_conditional_skip": ("C A", "z: 0\nn: 0\nram: {}"),
    # z=1, then conditionally skip A (should not skip)
    "c_command_no_skip_when_nonzero": ("A C A", "z: 2\nn: 0\nram: {}"),
    # All three A commands executed (goto doesn't skip as expected)
    "goto_command_jump": ("A 3 A A", "z: 3\nn: 0\nram: {}"),
    # Store 2 at address 1, 6 at address 4
    "multiple_memory_locations": (
        "A N A S A A N A A S",
        "z: 6\nn: 4\nram: {\n    1: 2,\n    4: 6\n}",
    ),
    "empty_program": ("", "z: 0\nn: 0\nram: {}"),
    # Only A command executes, but L command loads from uninitialized address
    "invalid_commands_ignored": (
        "A invalid B C D E F G H I J K L M O P Q R T U V W X Y Z",
        "z: 0\nn: 0\nram: {}",
    ),
    "comments_in_code": (
        "A /* comment */ A // another comment A",
        "z: 3\nn: 0\nram: {}",
    ),
    # A skipped goto 0 is harmless; leading zeros are decimal (004 is 4).
    "skipped_goto_zero": ("C 0 A", "z: 1\nn: 0\nram: {}"),
    "leading_zero_goto": ("Z 004 A A", "z: 1\nn: 0\nram: {}"),
    # Jump to non-existent instruction: terminates after first A
    "large_goto_number": ("A 999 A", "z: 1\nn: 0\nram: {}"),
}


@pytest.mark.parametrize(("code", "expected"), _DUMPS.values(), ids=list(_DUMPS))
def test_dump(code: str, expected: str) -> None:
    assert dump(code) == expected


def test_goto_zero_names_no_command() -> None:
    """Digits are not comments ("characters other than ZANCLS and digits")."""
    with pytest.raises(HaltError, match="count from 1"):
        dump("A A 0 A")


class TestStepMachine:
    def test_the_dump_flag_is_set_by_the_step_past_the_end(self) -> None:
        machine = _Machine("A", IO())
        machine.step()
        assert not machine.dumped
        machine.step()
        assert machine.dumped

    def test_load_reads_the_address_in_z(self) -> None:
        """L loads RAM at the address z holds, not at a fixed one."""
        from esolangs.languages.ram0.tests.oracle_checks import check_raw_ram0

        check_raw_ram0()
        machine = _Machine("A N S L", IO())
        while not machine.halted:
            machine.step()
        assert (machine.z, machine.ram) == (1, {1: 1})

    def test_conditional_skip_is_relative(self) -> None:
        """C skips the next command; it does not jump to a fixed index."""
        machine = _Machine("A Z C A A", IO())
        while not machine.halted:
            machine.step()
        # exactly one A was skipped: skipping none leaves 2, skipping both 0
        assert machine.z == 1

    def test_state_is_dumped_only_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stepping a halted machine again does not repeat the dump."""
        machine = _Machine("A", ScriptedIO(""))
        while not machine.halted:
            machine.step()
        machine.step()  # dumps
        machine.step()  # must not dump again
        assert machine.io.getvalue() == "z: 1\nn: 0\nram: {}"
        _check_dump_retry(monkeypatch)


def _machine(code: object) -> object:
    return _Machine(code, IO())


class TestContract(SnapshotContract, CycleContract, StateViewContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "A"
    halting_program = "ZA"
    looping_program = "Z1"
    # `Z` zeroes the accumulator and `A` increments it, so the cursor and
    # `z` move while `n` stays put -- three slots, not one read thrice.
    state_views = ("ind", "z", "n", "ip", "memory")
    # `S` is what moves `n`; "ZA" left it at its initial value.
    viewing_program = "A N S"


class TestStateViewValues:
    """The named views read the slots they claim, not one another."""

    def test_n_and_z_are_separate_registers(self) -> None:
        """One step in they differ; by the end of the run they agree."""
        machine = _machine("A N S")
        machine.step()
        assert (machine.z, machine.n) == (1, 0)


@pytest.mark.medium
def test_wide_gotos_keep_the_target_and_domain_faults() -> None:
    api = Language("RAM0")
    zeros = "0" * 641
    wide = "9" * 641
    expected = "z: 1\nn: 0\nram: {}"
    policy = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(640)
        for limits, isolated in (
            (None, False),
            (ExecutionLimits(max_steps=3), False),
            (ExecutionLimits(max_steps=3), True),
        ):
            for source, output, steps in (
                (f"A {wide} A", expected, 2),
                (f"A {zeros}3 A", "z: 2\nn: 0\nram: {}", 3),
                (f"C {zeros} A", expected, 2),
            ):
                observed = api.run(
                    source, stdin="unused", limits=limits, isolated=isolated
                )
                assert observed == ExecutionResult(
                    output,
                    0,
                    0,
                    0,
                    completion=POST_HALT_REPORT,
                    steps=None if limits is None else steps,
                )
            fault = api.execute(f"A {zeros} A", limits=limits, isolated=isolated)
            assert fault.status == "fault"
            assert type(fault.error) is HaltError
            assert (
                str(fault.error) == f"goto {zeros} at command 2: commands count from 1"
            )
            assert "jump to a command number of 1 or more" in " ".join(
                fault.error.__notes__
            )
            assert fault.observation == ExecutionResult(
                "", 0, 0, 0, steps=None if limits is None else 1
            )

        debugger = api.make_debugger(f"A {wide} A")
        debugger.step()
        debugger.step()
        assert debugger.halted
        assert debugger.ip == 10**641 - 2
    finally:
        sys.set_int_max_str_digits(policy)


def _check_dump_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    api = Language("RAM0")
    source = "A N A S 99 A"
    expected = "z: 2\nn: 1\nram: {\n    1: 2\n}"
    complete = ExecutionResult(expected, 0, 0, 0, completion=POST_HALT_REPORT, steps=5)
    clean = api.make_debugger(source, stdin="unused")
    assert clean.run(limits=ExecutionLimits(max_steps=5)) == "halted"
    assert clean.observation == complete

    write = ScriptedIO._write
    attempts: list[object] = []
    prefix = ""

    def reject_first(port: ScriptedIO, value: object) -> None:
        attempts.append(value)
        if len(attempts) == 1:
            write(port, prefix)
            raise HaltError("temporary dump refusal")
        write(port, value)

    limits = ExecutionLimits(max_steps=0)
    for accepted in (0, 2, len(expected)):
        attempts.clear()
        prefix = expected[:accepted]
        replay = api.make_debugger(source, stdin="unused")
        for _ in range(5):
            replay.step()
        assert replay.halted
        boundary = replay.snapshot()
        workspace = _capture_workspace(replay.vm)
        with monkeypatch.context() as scoped:
            scoped.setattr(ScriptedIO, "_write", reject_first)
            with pytest.raises(HaltError, match="dump refusal") as exc:
                replay.run(limits=limits)
            partial = replace(complete, output=prefix, completion=None)
            assert exc.value.observation == replay.observation == partial
            if accepted:
                assert replay.snapshot() == (*boundary, accepted)
                assert _capture_workspace(replay.vm).parts == (
                    *workspace.parts[:-1],
                    WorkspaceVariant("pending_output", (accepted,)),
                )
            else:
                assert replay.snapshot() == boundary
                assert _capture_workspace(replay.vm) == workspace
            assert replay.run(limits=limits) == "halted"
            replay.step()
        remaining = [expected[accepted:]] if accepted < len(expected) else []
        assert attempts == [expected, *remaining]
        assert replay.observation == complete
        assert replay.snapshot() == clean.snapshot()
        assert _capture_workspace(replay.vm) == _capture_workspace(clean.vm)
        assert exc.value.observation == partial
