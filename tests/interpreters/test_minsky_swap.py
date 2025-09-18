"""
Unit tests for Minsky Swap interpreter.

Tests cover all Minsky Swap commands, program flow control, and both compact and readable notation.
Minsky Swap is a Turing-complete esoteric language based on Minsky machines with two registers.
"""

import importlib.util
import io
import sys
from contextlib import redirect_stdout

spec = importlib.util.spec_from_file_location(
    "minsky_swap",
    "/Users/bangyen/Documents/repos/esolangs/src/esolangs/interpreters/register_based/minsky-swap.py",
)
assert spec is not None, "Failed to load module spec"
minsky_swap = importlib.util.module_from_spec(spec)
sys.modules["minsky_swap"] = minsky_swap
assert spec.loader is not None, "Module spec has no loader"
spec.loader.exec_module(minsky_swap)
run = minsky_swap.run


class TestMinskySwapBasicCommands:
    """Test basic Minsky Swap command functionality."""

    def test_increment_command(self) -> None:
        """Test + command increments the current register."""
        with redirect_stdout(io.StringIO()) as f:
            run("+")
        assert f.getvalue().strip() == "1 0"

        with redirect_stdout(io.StringIO()) as f:
            run("++")
        assert f.getvalue().strip() == "2 0"

    def test_swap_command(self) -> None:
        """Test * command swaps the register pointer."""
        with redirect_stdout(io.StringIO()) as f:
            run("*+")
        assert f.getvalue().strip() == "0 1"

        with redirect_stdout(io.StringIO()) as f:
            run("+*+")
        assert f.getvalue().strip() == "1 1"

    def test_decrement_jump_command(self) -> None:
        """Test ~ command decrements if nonzero, jumps if zero."""
        with redirect_stdout(io.StringIO()) as f:
            run("+~\n1")
        assert f.getvalue().strip() == "0 0"

        with redirect_stdout(io.StringIO()) as f:
            run("~\n1")
        assert f.getvalue().strip() == "0 0"

    def test_jump_targets(self) -> None:
        """Test jump targets from the jump line."""
        with redirect_stdout(io.StringIO()) as f:
            run("~+~\n2 1")
        assert f.getvalue().strip() == "0 0"

    def test_empty_program(self) -> None:
        """Test empty program outputs zeros."""
        with redirect_stdout(io.StringIO()) as f:
            run("")
        assert f.getvalue().strip() == "0 0"

    def test_whitespace_ignored(self) -> None:
        """Test that whitespace and non-command characters are ignored."""
        with redirect_stdout(io.StringIO()) as f:
            run("  +  \n  ")
        assert f.getvalue().strip() == "1 0"


class TestMinskySwapReadableNotation:
    """Test readable Minsky Swap notation (RMSN)."""

    def test_inc_command(self) -> None:
        """Test inc() command in readable notation."""
        with redirect_stdout(io.StringIO()) as f:
            run("inc();")
        assert f.getvalue().strip() == "1 0"

        with redirect_stdout(io.StringIO()) as f:
            run("inc(); inc();")
        assert f.getvalue().strip() == "2 0"

    def test_swap_command_readable(self) -> None:
        """Test swap() command in readable notation."""
        with redirect_stdout(io.StringIO()) as f:
            run("swap(); inc();")
        assert f.getvalue().strip() == "0 1"

    def test_decnz_command(self) -> None:
        """Test decnz() command in readable notation."""
        with redirect_stdout(io.StringIO()) as f:
            run("inc(); decnz(1);")
        assert f.getvalue().strip() == "0 0"

        with redirect_stdout(io.StringIO()) as f:
            run("decnz(1); inc();")
        assert f.getvalue().strip() == "1 0"

    def test_mixed_notation(self) -> None:
        """Test mixing compact and readable notation."""
        with redirect_stdout(io.StringIO()) as f:
            run("inc(); +")
        assert f.getvalue().strip() == "2 0"


class TestMinskySwapProgramFlow:
    """Test program flow control and complex programs."""

    def test_simple_loop(self) -> None:
        """Test a simple counting loop."""
        with redirect_stdout(io.StringIO()) as f:
            run("+++~\n1")
        assert f.getvalue().strip() == "2 0"

    def test_register_swapping_loop(self) -> None:
        """Test program that swaps between registers."""
        with redirect_stdout(io.StringIO()) as f:
            run("+*+*+")
        assert f.getvalue().strip() == "2 1"

    def test_conditional_jump(self) -> None:
        """Test conditional jump based on register value."""
        with redirect_stdout(io.StringIO()) as f:
            run("++~+~\n2 1")
        assert f.getvalue().strip() == "1 0"

    def test_complex_program(self) -> None:
        """Test a more complex program with multiple operations."""
        with redirect_stdout(io.StringIO()) as f:
            run("++*++*+++")
        assert f.getvalue().strip() == "5 2"


class TestMinskySwapEdgeCases:
    """Test edge cases and error conditions."""

    def test_no_jump_line(self) -> None:
        """Test program with no jump line."""
        with redirect_stdout(io.StringIO()) as f:
            run("+")
        assert f.getvalue().strip() == "1 0"

    def test_empty_jump_line(self) -> None:
        """Test program with empty jump line."""
        with redirect_stdout(io.StringIO()) as f:
            run("+\n")
        assert f.getvalue().strip() == "1 0"

    def test_invalid_jump_target(self) -> None:
        """Test program with invalid jump target (should not crash)."""
        with redirect_stdout(io.StringIO()) as f:
            run("~\n999")
        assert f.getvalue().strip() == "0 0"

    def test_multiple_tildes(self) -> None:
        """Test program with multiple tildes and jump targets."""
        with redirect_stdout(io.StringIO()) as f:
            run("~+~+~\n3 2 1")
        assert f.getvalue().strip() == "0 0"

    def test_register_overflow_simulation(self) -> None:
        """Test that registers can handle large values."""
        with redirect_stdout(io.StringIO()) as f:
            run("+" * 1000)
        assert f.getvalue().strip() == "1000 0"


class TestMinskySwapExamples:
    """Test example programs and common patterns."""

    def test_hello_world_pattern(self) -> None:
        """Test a simple pattern that could be used for output."""
        with redirect_stdout(io.StringIO()) as f:
            run("+++*+++")
        assert f.getvalue().strip() == "3 3"

    def test_register_copy_pattern(self) -> None:
        """Test copying value between registers."""
        with redirect_stdout(io.StringIO()) as f:
            run("+++*+++*~+~\n2 1")
        assert f.getvalue().strip() == "2 3"

    def test_readable_notation_example(self) -> None:
        """Test a complete readable notation example."""
        program = """
        inc();
        swap();
        inc();
        inc();
        swap();
        decnz(1);
        """
        with redirect_stdout(io.StringIO()) as f:
            run(program)
        assert f.getvalue().strip() == "0 2"
