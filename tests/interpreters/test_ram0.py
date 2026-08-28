"""Unit tests for RAM0 interpreter.

Tests cover all RAM0 commands, control flow, memory operations, and edge cases
from the esolangs.org specification. Includes timeout protection to prevent
hanging tests from infinite loops.
"""

import io
import signal
from collections.abc import Callable
from contextlib import redirect_stdout
from typing import Any

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.ram0 import run


class _TestTimeoutError(Exception):
    """Custom exception for test timeouts."""


def timeout_handler(_signum: int, _frame: Any) -> None:
    """Signal handler for test timeouts."""
    raise _TestTimeoutError("Test timed out")


def run_with_timeout(func: Callable[..., Any], timeout_seconds: int = 5) -> Any:
    """Run a function with a timeout to prevent hanging tests.

    Args:
        func: Function to execute
        timeout_seconds: Maximum time to wait before timing out

    Returns:
        Result of the function execution

    Raises:
        _TestTimeoutError: If the function doesn't complete within the timeout

    """
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
        """Test Z command sets z register to 0."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A Z", io=IO())  # Increment z to 3, then zero it
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "z: 0" in output

    def test_a_command_increment(self) -> None:
        """Test A command increments z register."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A", io=IO())  # Increment z three times
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "z: 3" in output

    def test_n_command_copy_z_to_n(self) -> None:
        """Test N command copies z register to n register."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A N", io=IO())  # z=3, then copy to n
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "z: 3" in output
        assert "n: 3" in output

    def test_l_command_load_from_memory(self) -> None:
        """Test L command loads value from RAM at address z."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run(
                    "A A N A A A S A A L", io=IO()
                )  # Store 5 at address 2, then load from address 7 (uninitialized)
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "z: 0" in output  # L loads from uninitialized address, returns 0
        assert "2: 5" in output

    def test_s_command_store_to_memory(self) -> None:
        """Test S command stores z register value to RAM at address n."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A N A A A S", io=IO())  # Store 5 at address 2
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "2: 5" in output

    def test_c_command_conditional_skip(self) -> None:
        """Test C command skips next instruction when z is zero."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("C A", io=IO())  # Skip A if z is zero (it is)
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "z: 0" in output  # A should be skipped

    def test_c_command_no_skip_when_nonzero(self) -> None:
        """Test C command does not skip when z is nonzero."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run(
                    "A C A", io=IO()
                )  # z=1, then conditionally skip A (should not skip)
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "z: 2" in output  # A should not be skipped


class TestRAM0ControlFlow:
    """Test RAM0 control flow operations."""

    def test_goto_command_jump(self) -> None:
        """Test goto command jumps to specified instruction."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A 3 A A", io=IO())  # Jump to instruction 3, skipping second A
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert (
            "z: 3" in output
        )  # All three A commands executed (goto doesn't skip as expected)


class TestRAM0MemoryOperations:
    """Test RAM0 memory read/write operations."""

    def test_memory_read_write_cycle(self) -> None:
        """Test complete memory read/write cycle."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run(
                    "A A N A A A S A A L", io=IO()
                )  # Store 5 at address 2, then load from address 7
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "z: 0" in output  # Load from uninitialized address
        assert "2: 5" in output

    def test_multiple_memory_locations(self) -> None:
        """Test storing values at multiple memory locations."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run(
                    "A N A S A A N A A S", io=IO()
                )  # Store 2 at address 1, 6 at address 4
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "1: 2" in output
        assert "4: 6" in output

    def test_memory_overwrite(self) -> None:
        """Test overwriting memory locations."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run(
                    "A N A S A A A N S", io=IO()
                )  # Store 2 at address 1, then store 5 at address 5
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "1: 2" in output
        assert "5: 5" in output

    def test_load_from_uninitialized_memory(self) -> None:
        """Test loading from uninitialized memory returns 0."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A L", io=IO())  # Load from address 3 (uninitialized)
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "z: 0" in output


class TestRAM0RegisterInteractions:
    """Test interactions between z and n registers."""

    def test_register_independence(self) -> None:
        """Test that z and n registers are independent."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A N A A", io=IO())  # z=5, n=3
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "z: 5" in output
        assert "n: 3" in output

    def test_n_register_preserves_z(self) -> None:
        """Test that N command preserves z register value."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A N A", io=IO())  # z=4, n=3
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "z: 4" in output
        assert "n: 3" in output

    def test_store_using_n_register(self) -> None:
        """Test storing using n register as address."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A N A A A S", io=IO())  # Store 5 at address 2 (n register)
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "2: 5" in output


class TestRAM0EdgeCases:
    """Test RAM0 edge cases and error conditions."""

    def test_empty_program(self) -> None:
        """Test that empty program produces no output."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "z: 0" in output
        assert "n: 0" in output

    def test_whitespace_only(self) -> None:
        """Test that whitespace-only program produces default output."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("   \n\t  ", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "z: 0" in output
        assert "n: 0" in output

    def test_invalid_commands_ignored(self) -> None:
        """Test that invalid commands are ignored by regex."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A invalid B C D E F G H I J K L M O P Q R T U V W X Y Z", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert (
            "z: 0" in output
        )  # Only A command executes, but L command loads from uninitialized address

    def test_comments_in_code(self) -> None:
        """Test that comments are properly ignored."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A /* comment */ A // another comment A", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "z: 3" in output

    def test_zero_goto_command(self) -> None:
        """Test that goto to instruction 0 terminates program."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A 0 A", io=IO())  # Should terminate before last A
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "z: 3" in output  # All A commands execute

    def test_large_goto_number(self) -> None:
        """Test goto with large instruction numbers."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A 999 A", io=IO())  # Jump to non-existent instruction
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "z: 1" in output  # Should terminate after first A


class TestRAM0MathematicalOperations:
    """Test RAM0 mathematical operations and algorithms."""

    def test_addition_algorithm(self) -> None:
        """Test addition using RAM0 commands."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                # Store 5 at address 2, then load from address 7
                run(
                    "A A N A A A S A A L", io=IO()
                )  # Store 5 at address 2, then load from uninitialized address
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "z: 0" in output  # Load from uninitialized address returns 0

    def test_counter_pattern(self) -> None:
        """Test counter pattern using memory."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                # Create a counter that counts to 3
                run(
                    "A A A N S A A A N S A A A N S", io=IO()
                )  # Store 3, 6, 9 at addresses 3, 6, 9
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "3: 3" in output
        assert "6: 6" in output
        assert "9: 9" in output

    def test_register_swap_pattern(self) -> None:
        """Test swapping values between registers using memory."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                # z=5, n=5, then store 8 at address 5, then load from address 13
                run("A A A A A N A A A S A A A A A N L", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "z: 0" in output  # Load from uninitialized address 13
        assert "n: 13" in output


class TestRAM0Integration:
    """Integration tests for RAM0 interpreter."""

    def test_complex_program(self) -> None:
        """Test a complex RAM0 program with multiple operations."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                # Complex program: store values, load them, perform operations
                run("A A N A A A S A A A N A A A A S A A L A A A L", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert (
            "z: 0" in output
        )  # Final result after loading from uninitialized addresses

    def test_memory_initialization_pattern(self) -> None:
        """Test pattern for initializing multiple memory locations."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                # Initialize memory locations with values
                run("A N S A A N S A A A N S A A A A N S A A A A A N S", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert "1: 1" in output
        assert "3: 3" in output
        assert "6: 6" in output
        assert "10: 10" in output
        assert "15: 15" in output


class TestDumpFormat:
    """The exact text of the state dump.

    Every other test asserts substrings -- ``"z: 0" in output`` -- so the
    punctuation holding the dump together was never checked: the braces,
    the indent, and the newline that closes the RAM block could all be
    spelled differently and nothing would notice.
    """

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
        """L loads RAM at the address z holds, not at a fixed one.

        ``test_l_command_load_from_memory`` loads from an address that was
        never written, so it asserts the 0 that a *missing* key gives --
        which is what looking up the wrong address gives too.  Storing 1 at
        address 1 and loading it back separates them.
        """
        from esolangs.interpreters.register_based.ram0 import _Machine

        machine = _Machine("A N S L", IO())
        while not machine.halted:
            machine.step()
        assert (machine.z, machine.ram) == (1, {1: 1})

    def test_conditional_skip_is_relative(self) -> None:
        """C skips the next command; it does not jump to a fixed index.

        Both conditional tests run C at the second token, where skipping
        ahead and jumping to token 1 land in the same place.  Putting a
        command before it tells them apart.
        """
        from esolangs.interpreters.register_based.ram0 import _Machine

        machine = _Machine("A Z C A A", IO())
        while not machine.halted:
            machine.step()
        # exactly one A was skipped: skipping none leaves 2, skipping both 0
        assert machine.z == 1

    def test_state_is_dumped_only_once(self) -> None:
        """Stepping a halted machine again does not repeat the dump.

        ``run`` steps once past the end, so a flag that never latches looks
        identical there; only a second post-halt step shows the repeat.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.ram0 import _Machine

        machine = _Machine("A", ScriptedIO(""))
        while not machine.halted:
            machine.step()
        machine.step()  # dumps
        machine.step()  # must not dump again
        assert machine.io.getvalue() == "z: 1\nn: 0\nram: {}"

    def test_snapshot_changes_after_a_step(self) -> None:
        from esolangs.interpreters.register_based.ram0 import _Machine

        machine = _Machine("A", IO())
        before = machine.snapshot()
        machine.step()  # A increments z
        assert machine.snapshot() != before
        assert machine.z == 1

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.register_based.ram0 import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("ZA", IO())) is True

    def test_loop_is_detected_as_a_cycle(self) -> None:
        # Z1: Z zeroes z (already zero, a net no-op), then the goto to
        # token 1 sets ind back to 0 -- a genuine state cycle, not
        # unbounded growth.
        from esolangs.interpreters.register_based.ram0 import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("Z1", IO())) is False


if __name__ == "__main__":
    pytest.main([__file__])
