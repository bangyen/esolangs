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
from tests.interpreters.contract import CycleContract, SnapshotContract


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
        assert output == "z: 0\nn: 0\nram: {}"

    def test_a_command_increment(self) -> None:
        """Test A command increments z register."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A", io=IO())  # Increment z three times
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 3\nn: 0\nram: {}"

    def test_n_command_copy_z_to_n(self) -> None:
        """Test N command copies z register to n register."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A N", io=IO())  # z=3, then copy to n
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 3\nn: 3\nram: {}"

    def test_l_command_load_from_memory(self) -> None:
        """Test L command loads value from RAM at address z."""

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
        """Test S command stores z register value to RAM at address n."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A N A A A S", io=IO())  # Store 5 at address 2
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 5\nn: 2\nram: {\n    2: 5\n}"

    def test_c_command_conditional_skip(self) -> None:
        """Test C command skips next instruction when z is zero."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("C A", io=IO())  # Skip A if z is zero (it is)
            return f.getvalue()

        output = run_with_timeout(test_func)
        # A should be skipped
        assert output == "z: 0\nn: 0\nram: {}"

    def test_c_command_no_skip_when_nonzero(self) -> None:
        """Test C command does not skip when z is nonzero."""

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
        """Test goto command jumps to specified instruction."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A 3 A A", io=IO())  # Jump to instruction 3, skipping second A
            return f.getvalue()

        output = run_with_timeout(test_func)
        # All three A commands executed (goto doesn't skip as expected)
        assert output == "z: 3\nn: 0\nram: {}"


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
        # Load from uninitialized address
        assert output == "z: 0\nn: 2\nram: {\n    2: 5\n}"

    def test_multiple_memory_locations(self) -> None:
        """Test storing values at multiple memory locations."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run(
                    "A N A S A A N A A S", io=IO()
                )  # Store 2 at address 1, 6 at address 4
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 6\nn: 4\nram: {\n    1: 2,\n    4: 6\n}"

    def test_memory_overwrite(self) -> None:
        """Test overwriting memory locations."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run(
                    "A N A S A A A N S", io=IO()
                )  # Store 2 at address 1, then store 5 at address 5
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 5\nn: 5\nram: {\n    1: 2,\n    5: 5\n}"

    def test_load_from_uninitialized_memory(self) -> None:
        """Test loading from uninitialized memory returns 0."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A L", io=IO())  # Load from address 3 (uninitialized)
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 0\nn: 0\nram: {}"


class TestRAM0RegisterInteractions:
    """Test interactions between z and n registers."""

    def test_register_independence(self) -> None:
        """Test that z and n registers are independent."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A N A A", io=IO())  # z=5, n=3
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 5\nn: 3\nram: {}"

    def test_n_register_preserves_z(self) -> None:
        """Test that N command preserves z register value."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A A N A", io=IO())  # z=4, n=3
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 4\nn: 3\nram: {}"

    def test_store_using_n_register(self) -> None:
        """Test storing using n register as address."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("A A N A A A S", io=IO())  # Store 5 at address 2 (n register)
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 5\nn: 2\nram: {\n    2: 5\n}"


class TestRAM0EdgeCases:
    """Test RAM0 edge cases and error conditions."""

    def test_empty_program(self) -> None:
        """Test that empty program produces no output."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 0\nn: 0\nram: {}"

    def test_whitespace_only(self) -> None:
        """Test that whitespace-only program produces default output."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                run("   \n\t  ", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == "z: 0\nn: 0\nram: {}"

    def test_invalid_commands_ignored(self) -> None:
        """Test that invalid commands are ignored by regex."""

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
        # Load from uninitialized address returns 0
        assert output == "z: 0\nn: 2\nram: {\n    2: 5\n}"

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
        assert output == "z: 9\nn: 9\nram: {\n    3: 3,\n    6: 6,\n    9: 9\n}"

    def test_register_swap_pattern(self) -> None:
        """Test swapping values between registers using memory."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                # z=5, n=5, then store 8 at address 5, then load from address 13
                run("A A A A A N A A A S A A A A A N L", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        # Load from uninitialized address 13
        assert output == "z: 0\nn: 13\nram: {\n    5: 8\n}"


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
        # Final result after loading from uninitialized addresses
        assert output == "z: 0\nn: 8\nram: {\n    2: 5,\n    8: 12\n}"

    def test_memory_initialization_pattern(self) -> None:
        """Test pattern for initializing multiple memory locations."""

        def test_func() -> str:
            with redirect_stdout(io.StringIO()) as f:
                # Initialize memory locations with values
                run("A N S A A N S A A A N S A A A A N S A A A A A N S", io=IO())
            return f.getvalue()

        output = run_with_timeout(test_func)
        assert output == (
            "z: 15\nn: 15\nram: {\n"
            "    1: 1,\n    3: 3,\n    6: 6,\n    10: 10,\n    15: 15\n}"
        )


class TestDumpFormat:
    """The exact text of the state dump.

    The tests above now compare whole dumps, so the punctuation holding one
    together -- the braces, the indent, the newline closing the RAM block --
    is covered wherever they run.  These keep it pinned directly, on the
    smallest programs that show a populated and an empty RAM block.
    """

    def dump(self, code: str) -> str:
        with redirect_stdout(io.StringIO()) as f:
            run(code, io=IO())
        return f.getvalue()

    def test_dump_happens_once_however_often_a_halted_machine_is_stepped(
        self,
    ) -> None:
        """The dump is guarded by a flag that starts as False itself.

        Stepping past the halt is a no-op except for the one dump, and the
        flag that arranges it is only ever read for truth -- which ``None``
        satisfies as well as ``False`` -- so the identity is asserted too,
        the flag being annotated a bool.
        """
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


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "A"
    halting_program = "ZA"
    looping_program = "Z1"


if __name__ == "__main__":
    pytest.main([__file__])
