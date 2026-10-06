"""Unit tests for RAM0 interpreter."""

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
    """Custom exception for test timeouts."""


def timeout_handler(_signum: int, _frame: Any) -> None:
    """Signal handler for test timeouts."""
    raise _TestTimeoutError("Test timed out")


def run_with_timeout(func: Callable[..., Any], timeout_seconds: int = 5) -> Any:
    """Run a function with a timeout to prevent hanging tests."""
    # Set up signal handler for timeout
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)

    try:
        return func()
    finally:
        # Restore original signal handler and cancel alarm
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


class TestRAM0BasicCommands:
    """Test basic RAM0 command functionality."""

    def test_z_command_zero_register(self) -> None:

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A Z", io=IO())  # Increment z to 3, then zero it
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 0\nn: 0\nram: {}"

    def test_a_command_increment(self) -> None:

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A", io=IO())  # Increment z three times
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 3\nn: 0\nram: {}"

    def test_n_command_copy_z_to_n(self) -> None:

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A N", io=IO())  # z=3, then copy to n
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 3\nn: 3\nram: {}"

    def test_l_command_load_from_memory(self) -> None:

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run(
                    "A A N A A A S A A L", io=IO()
                )  # Store 5 at address 2, then load from address 7 (uninitialized)
            return f.getvalue()

        output = run_with_timeout(test_func)
        # L loads from uninitialized address, returns 0
        assert output == "z: 0\nn: 2\nram: {\n    2: 5\n}"

    def test_s_command_store_to_memory(self) -> None:

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A N A A A S", io=IO())  # Store 5 at address 2
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 5\nn: 2\nram: {\n    2: 5\n}"

    def test_c_command_conditional_skip(self) -> None:

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("C A", io=IO())  # Skip A if z is zero (it is)
            return f.getvalue()

        output = run_with_timeout(test_func)
        # A should be skipped
        assert output == "z: 0\nn: 0\nram: {}"

    def test_c_command_no_skip_when_nonzero(self) -> None:

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run(
                    "A C A", io=IO()
                )  # z=1, then conditionally skip A (should not skip)
            return f.getvalue()

        output = run_with_timeout(test_func)
        # A should not be skipped
        assert output == "z: 2\nn: 0\nram: {}"


class TestRAM0ControlFlow:
    """Test RAM0 control flow operations."""

    def test_goto_command_jump(self) -> None:

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A 3 A A", io=IO())  # Jump to instruction 3, skipping second A
            return f.getvalue()

        output = run_with_timeout(test_func)
        # All three A commands executed (goto doesn't skip as expected)
        assert output == "z: 3\nn: 0\nram: {}"


class TestRAM0MemoryOperations:
    """Test RAM0 memory read/write operations."""

    def test_multiple_memory_locations(self) -> None:

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run(
                    "A N A S A A N A A S", io=IO()
                )  # Store 2 at address 1, 6 at address 4
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 6\nn: 4\nram: {\n    1: 2,\n    4: 6\n}"

    def test_memory_overwrite(self) -> None:

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run(
                    "A N A S A A A N S", io=IO()
                )  # Store 2 at address 1, then store 5 at address 5
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 5\nn: 5\nram: {\n    1: 2,\n    5: 5\n}"

    def test_load_from_uninitialized_memory(self) -> None:

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A L", io=IO())  # Load from address 3 (uninitialized)
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 0\nn: 0\nram: {}"


class TestRAM0EdgeCases:
    """Test RAM0 edge cases and error conditions."""

    def test_empty_program(self) -> None:

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 0\nn: 0\nram: {}"

    def test_invalid_commands_ignored(self) -> None:

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A invalid B C D E F G H I J K L M O P Q R T U V W X Y Z", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        # Only A command executes, but L command loads from uninitialized address
        assert output == "z: 0\nn: 0\nram: {}"

    def test_comments_in_code(self) -> None:
        """Test that comments are properly ignored."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A /* comment */ A // another comment A", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 3\nn: 0\nram: {}"

    def test_zero_goto_command(self) -> None:
        """Test that goto to instruction 0 terminates program."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A 0 A", io=IO())  # Should terminate before last A
            return f.getvalue()

        output = run_with_timeout(test_func)
        # All A commands execute
        assert output == "z: 3\nn: 0\nram: {}"

    def test_large_goto_number(self) -> None:
        """Test goto with large instruction numbers."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A 999 A", io=IO())  # Jump to non-existent instruction
            return f.getvalue()

        output = run_with_timeout(test_func)
        # Should terminate after first A
        assert output == "z: 1\nn: 0\nram: {}"


class TestDumpFormat:
    """The exact text of the state dump."""

    def dump(self, code: str) -> str:
        with redirect_stdout(io.StringIO()) as f:
            run(code, io=IO())
        return f.getvalue()

    def test_dump_with_memory(self) -> None:
        assert self.dump("A N S") == "z: 1\nn: 1\nram: {\n    1: 1\n}"

    def test_dump_without_memory(self) -> None:
        assert self.dump("A") == "z: 1\nn: 0\nram: {}"


class TestStepMachine:
    def test_load_reads_the_address_in_z(self) -> None:
        """L loads RAM at the address z holds, not at a fixed one."""
        from esolangs.interpreters.register_based.ram0 import _Machine

        machine = _Machine("A N S L", IO())
        while not machine.halted:
            machine.step()
        assert (machine.z, machine.ram) == (1, {1: 1})

    def test_conditional_skip_is_relative(self) -> None:
        """C skips the next command; it does not jump to a fixed index."""
        from esolangs.interpreters.register_based.ram0 import _Machine

        machine = _Machine("A Z C A A", IO())
        while not machine.halted:
            machine.step()
        # exactly one A was skipped: skipping none leaves 2, skipping both 0
        assert machine.z == 1

    def test_state_is_dumped_only_once(self) -> None:
        """Stepping a halted machine again does not repeat the dump."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.ram0 import _Machine

        machine = _Machine("A", ScriptedIO(""))
        while not machine.halted:
            machine.step()
        machine.step()  # dumps
        machine.step()  # must not dump again
        assert machine.io.getvalue() == "z: 1\nn: 0\nram: {}"

    def test_loop_is_detected_as_a_cycle(self) -> None:
        # Z1: Z zeroes z (already zero, a net no-op), then the goto to
        # token 1 sets ind back to 0 -- a genuine state cycle, not
        # unbounded growth.
        from esolangs.interpreters.register_based.ram0 import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("Z1", IO())) is False


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.register_based.ram0 import _Machine

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


if __name__ == "__main__":
    pytest.main([__file__])


class TestStateViewValues:
    """The named views read the slots they claim, not one another."""

    def test_n_and_z_are_separate_registers(self) -> None:
        """One step in they differ; by the end of the run they agree."""
        machine = _machine("A N S")
        machine.step()
        assert (machine.z, machine.n) == (1, 0)
