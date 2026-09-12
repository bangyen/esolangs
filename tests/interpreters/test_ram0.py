r"""Unit tests for RAM0 interpreter."""

import io
import signal
from collections.abc import Callable
from contextlib import redirect_stdout
from typing import Any

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.ram0 import run
from tests.interpreters.contract import (
    CycleContract,
    SnapshotContract,
    StateViewContract,
)


class _TestTimeoutError(Exception):
    r"""Custom exception for test timeouts."""


def timeout_handler(_signum: int, _frame: Any) -> None:
    r"""Signal handler for test timeouts."""
    raise _TestTimeoutError("Test timed out")


def run_with_timeout(func: Callable[..., Any], timeout_seconds: int = 5) -> Any:
    r"""Run a function with a timeout to prevent hanging tests."""
    # Set up signal handler for.
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)

    try:
        return func()
    finally:
        # Restore original signal.
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


class TestRAM0BasicCommands:
    r"""Test basic RAM0 command functionality."""

    def test_z_command_zero_register(self) -> None:
        r"""Test Z command sets z register to 0."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A Z", io=IO())  # Increment z to 3, then zero.
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 0\nn: 0\nram: {}"

    def test_a_command_increment(self) -> None:
        r"""Test A command increments z register."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A", io=IO())  # Increment z three times.
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 3\nn: 0\nram: {}"

    def test_n_command_copy_z_to_n(self) -> None:
        r"""Test N command copies z register to n register."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A N", io=IO())  # z=3, then copy to n.
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 3\nn: 3\nram: {}"

    def test_l_command_load_from_memory(self) -> None:
        r"""Test L command loads value from RAM at address z."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A N A A A S A A L", io=IO())  # Store 5 at address 2, then.
            return f.getvalue()

        output = run_with_timeout(test_func)
        # L loads from uninitialized.
        assert output == "z: 0\nn: 2\nram: {\n    2: 5\n}"

    def test_s_command_store_to_memory(self) -> None:
        r"""Test S command stores z register value to RAM at address n."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A N A A A S", io=IO())  # Store 5 at address 2.
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 5\nn: 2\nram: {\n    2: 5\n}"

    def test_c_command_conditional_skip(self) -> None:
        r"""Test C command skips next instruction when z is zero."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("C A", io=IO())  # Skip A if z is zero (it is).
            return f.getvalue()

        output = run_with_timeout(test_func)
        # A should be skipped.
        assert output == "z: 0\nn: 0\nram: {}"

    def test_c_command_no_skip_when_nonzero(self) -> None:
        r"""Test C command does not skip when z is nonzero."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A C A", io=IO())  # z=1, then conditionally skip.
            return f.getvalue()

        output = run_with_timeout(test_func)
        # A should not be skipped.
        assert output == "z: 2\nn: 0\nram: {}"


class TestRAM0ControlFlow:
    r"""Test RAM0 control flow operations."""

    def test_goto_command_jump(self) -> None:
        r"""Test goto command jumps to specified instruction."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A 3 A A", io=IO())  # Jump to instruction 3,.
            return f.getvalue()

        output = run_with_timeout(test_func)
        # All three A commands executed.
        assert output == "z: 3\nn: 0\nram: {}"


class TestRAM0MemoryOperations:
    r"""Test RAM0 memory read/write operations."""

    def test_multiple_memory_locations(self) -> None:
        r"""Test storing values at multiple memory locations."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A N A S A A N A A S", io=IO())  # Store 2 at address 1, 6 at.
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 6\nn: 4\nram: {\n    1: 2,\n    4: 6\n}"

    def test_memory_overwrite(self) -> None:
        r"""Test overwriting memory locations."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A N A S A A A N S", io=IO())  # Store 2 at address 1, then.
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 5\nn: 5\nram: {\n    1: 2,\n    5: 5\n}"

    def test_load_from_uninitialized_memory(self) -> None:
        r"""Test loading from uninitialized memory returns 0."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A L", io=IO())  # Load from address 3.
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 0\nn: 0\nram: {}"


class TestRAM0RegisterInteractions:
    r"""Test interactions between z and n registers."""

    def test_register_independence(self) -> None:
        r"""Test that z and n registers are independent."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A N A A", io=IO())  # z=5, n=3.
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 5\nn: 3\nram: {}"

    def test_n_register_preserves_z(self) -> None:
        r"""Test that N command preserves z register value."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A N A", io=IO())  # z=4, n=3.
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 4\nn: 3\nram: {}"


class TestRAM0EdgeCases:
    r"""Test RAM0 edge cases and error conditions."""

    def test_empty_program(self) -> None:
        r"""Test that empty program produces no output."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 0\nn: 0\nram: {}"

    def test_whitespace_only(self) -> None:
        r"""Test that whitespace-only program produces default output."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("   \n\t  ", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 0\nn: 0\nram: {}"

    def test_invalid_commands_ignored(self) -> None:
        r"""Test that invalid commands are ignored by regex."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A invalid B C D E F G H I J K L M O P Q R T U V W X Y Z", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        # Only A command executes, but.
        assert output == "z: 0\nn: 0\nram: {}"

    def test_comments_in_code(self) -> None:
        r"""Test that comments are properly ignored."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A /* comment */ A // another comment A", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 3\nn: 0\nram: {}"

    def test_zero_goto_command(self) -> None:
        r"""Test that goto to instruction 0 terminates program."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A 0 A", io=IO())  # Should terminate before last.
            return f.getvalue()

        output = run_with_timeout(test_func)
        # All A commands execute.
        assert output == "z: 3\nn: 0\nram: {}"

    def test_large_goto_number(self) -> None:
        r"""Test goto with large instruction numbers."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A 999 A", io=IO())  # Jump to non-existent.
            return f.getvalue()

        output = run_with_timeout(test_func)
        # Should terminate after first.
        assert output == "z: 1\nn: 0\nram: {}"


class TestRAM0MathematicalOperations:
    r"""Test RAM0 mathematical operations and algorithms."""

    def test_counter_pattern(self) -> None:
        r"""Test counter pattern using memory."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                # Create a counter that counts.
                run(
                    "A A A N S A A A N S A A A N S", io=IO()
                )  # Store 3, 6, 9 at addresses 3,.
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 9\nn: 9\nram: {\n    3: 3,\n    6: 6,\n    9: 9\n}"

    def test_register_swap_pattern(self) -> None:
        r"""Test swapping values between registers using memory."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                # z=5, n=5, then store 8 at.
                run("A A A A A N A A A S A A A A A N L", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        # Load from uninitialized.
        assert output == "z: 0\nn: 13\nram: {\n    5: 8\n}"


class TestRAM0Integration:
    r"""Integration tests for RAM0 interpreter."""

    def test_complex_program(self) -> None:
        r"""Test a complex RAM0 program with multiple operations."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                # Complex program: store.
                run("A A N A A A S A A A N A A A A S A A L A A A L", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        # Final result after loading.
        assert output == "z: 0\nn: 8\nram: {\n    2: 5,\n    8: 12\n}"

    def test_memory_initialization_pattern(self) -> None:
        r"""Test pattern for initializing multiple memory locations."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                # Initialize memory locations.
                run("A N S A A N S A A A N S A A A A N S A A A A A N S", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == (
            "z: 15\nn: 15\nram: {\n"
            "    1: 1,\n    3: 3,\n    6: 6,\n    10: 10,\n    15: 15\n}"
        )


class TestDumpFormat:
    r"""The exact text of the state dump."""

    def dump(self, code: str) -> str:
        with redirect_stdout(io.StringIO()) as f:
            run(code, io=IO())
        return f.getvalue()

    def test_dump_happens_once_however_often_a_halted_machine_is_stepped(
        self,
    ) -> None:
        r"""The dump is guarded by a flag that starts as False itself."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.ram0 import _Machine

        machine = _Machine("A", ScriptedIO())
        assert machine.dumped is False
        while not machine.halted:
            machine.step()
        for _ in range(3):
            machine.step()
        assert machine.io.getvalue() == "z: 1\nn: 0\nram: {}"

    def test_dump_with_memory(self) -> None:
        assert self.dump("A N S") == "z: 1\nn: 1\nram: {\n    1: 1\n}"

    def test_dump_without_memory(self) -> None:
        assert self.dump("A") == "z: 1\nn: 0\nram: {}"


class TestStepMachine:
    def test_load_reads_the_address_in_z(self) -> None:
        r"""L loads RAM at the address z holds, not at a fixed one."""
        from esolangs.interpreters.register_based.ram0 import _Machine

        machine = _Machine("A N S L", IO())
        while not machine.halted:
            machine.step()
        assert (machine.z, machine.ram) == (1, {1: 1})

    def test_conditional_skip_is_relative(self) -> None:
        r"""C skips the next command; it does not jump to a fixed index."""
        from esolangs.interpreters.register_based.ram0 import _Machine

        machine = _Machine("A Z C A A", IO())
        while not machine.halted:
            machine.step()
        # exactly one A was skipped:.
        assert machine.z == 1

    def test_state_is_dumped_only_once(self) -> None:
        r"""Stepping a halted machine again does not repeat the dump."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.ram0 import _Machine

        machine = _Machine("A", ScriptedIO(""))
        while not machine.halted:
            machine.step()
        machine.step()  # dumps.
        machine.step()  # must not dump again.
        assert machine.io.getvalue() == "z: 1\nn: 0\nram: {}"

    def test_loop_is_detected_as_a_cycle(self) -> None:
        # Z1: Z zeroes z (already zero,.
        # token 1 sets ind back to 0 --.
        # unbounded growth.
        from esolangs.interpreters.register_based.ram0 import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("Z1", IO())) is False


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.register_based.ram0 import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract, CycleContract, StateViewContract):
    r"""The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "A"
    halting_program = "ZA"
    looping_program = "Z1"
    # `Z` zeroes the accumulator.
    # `z` move while `n` stays put.
    state_views = ("ind", "z", "n", "ip", "memory")
    # `S` is what moves `n`; "ZA".
    viewing_program = "A N S"


if __name__ == "__main__":
    pytest.main([__file__])


class TestStateViewValues:
    r"""The named views read the slots they claim, not one another."""

    def test_n_and_z_are_separate_registers(self) -> None:
        r"""One step in they differ; by the end of the run they agree."""
        machine = _machine("A N S")
        machine.step()
        assert (machine.z, machine.n) == (1, 0)
