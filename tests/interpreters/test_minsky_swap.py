"""Unit tests for Minsky Swap interpreter.

Tests cover all Minsky Swap commands, program flow control, and both compact
and readable notation.
Minsky Swap is a Turing-complete esoteric language based on Minsky machines
with two registers.
"""

import io
from contextlib import redirect_stdout

from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.minsky_swap import run
from tests.interpreters.contract import CycleContract, SnapshotContract


class TestMinskySwapBasicCommands:
    """Test basic Minsky Swap command functionality."""

    def test_increment_command(self) -> None:
        """Test + command increments the current register."""
        with redirect_stdout(io.StringIO()) as f:
            run("+", io=IO())
        assert f.getvalue().strip() == "1 0"

        with redirect_stdout(io.StringIO()) as f:
            run("++", io=IO())
        assert f.getvalue().strip() == "2 0"

    def test_swap_command(self) -> None:
        """Test * command swaps the register pointer."""
        with redirect_stdout(io.StringIO()) as f:
            run("*+", io=IO())
        assert f.getvalue().strip() == "0 1"

        with redirect_stdout(io.StringIO()) as f:
            run("+*+", io=IO())
        assert f.getvalue().strip() == "1 1"

    def test_decrement_jump_command(self) -> None:
        """Test ~ command decrements if nonzero, jumps if zero."""
        with redirect_stdout(io.StringIO()) as f:
            run("+~\n1", io=IO())
        assert f.getvalue().strip() == "0 0"

        with redirect_stdout(io.StringIO()) as f:
            run("~+\n2", io=IO())
        # ~ jumps to command 2 (the +) since the register is zero
        assert f.getvalue().strip() == "1 0"

    def test_jump_targets(self) -> None:
        """Test jump targets from the jump line."""
        with redirect_stdout(io.StringIO()) as f:
            run("~+~\n2 1", io=IO())
        assert f.getvalue().strip() == "0 0"

    def test_empty_program(self) -> None:
        """Test empty program outputs zeros."""
        with redirect_stdout(io.StringIO()) as f:
            run("", io=IO())
        assert f.getvalue().strip() == "0 0"

    def test_whitespace_ignored(self) -> None:
        """Test that whitespace and non-command characters are ignored."""
        with redirect_stdout(io.StringIO()) as f:
            run("  +  \n  ", io=IO())
        assert f.getvalue().strip() == "1 0"


class TestMinskySwapReadableNotation:
    """Test readable Minsky Swap notation (RMSN)."""

    def test_inc_command(self) -> None:
        """Test inc() command in readable notation."""
        with redirect_stdout(io.StringIO()) as f:
            run("inc();", io=IO())
        assert f.getvalue().strip() == "1 0"

        with redirect_stdout(io.StringIO()) as f:
            run("inc(); inc();", io=IO())
        assert f.getvalue().strip() == "2 0"

    def test_swap_command_readable(self) -> None:
        """Test swap() command in readable notation."""
        with redirect_stdout(io.StringIO()) as f:
            run("swap(); inc();", io=IO())
        assert f.getvalue().strip() == "0 1"

    def test_decnz_command(self) -> None:
        """Test decnz() command in readable notation."""
        with redirect_stdout(io.StringIO()) as f:
            run("inc(); decnz(1);", io=IO())
        assert f.getvalue().strip() == "0 0"

        with redirect_stdout(io.StringIO()) as f:
            run("decnz(2); inc();", io=IO())
        assert f.getvalue().strip() == "1 0"

    def test_mixed_notation(self) -> None:
        """Test mixing compact and readable notation."""
        with redirect_stdout(io.StringIO()) as f:
            run("inc(); +", io=IO())
        assert f.getvalue().strip() == "2 0"


class TestMinskySwapProgramFlow:
    """Test program flow control and complex programs."""

    def test_simple_loop(self) -> None:
        """Test a simple counting loop."""
        with redirect_stdout(io.StringIO()) as f:
            run("+++~\n1", io=IO())
        assert f.getvalue().strip() == "2 0"

    def test_register_swapping_loop(self) -> None:
        """Test program that swaps between registers."""
        with redirect_stdout(io.StringIO()) as f:
            run("+*+*+", io=IO())
        assert f.getvalue().strip() == "2 1"

    def test_conditional_jump(self) -> None:
        """Test conditional jump based on register value."""
        with redirect_stdout(io.StringIO()) as f:
            run("++~+~\n2 1", io=IO())
        assert f.getvalue().strip() == "1 0"

    def test_complex_program(self) -> None:
        """Test a more complex program with multiple operations."""
        with redirect_stdout(io.StringIO()) as f:
            run("++*++*+++", io=IO())
        assert f.getvalue().strip() == "5 2"


class TestMinskySwapEdgeCases:
    """Test edge cases and error conditions."""

    def test_no_jump_line(self) -> None:
        """Test program with no jump line."""
        with redirect_stdout(io.StringIO()) as f:
            run("+", io=IO())
        assert f.getvalue().strip() == "1 0"

    def test_empty_jump_line(self) -> None:
        """Test program with empty jump line."""
        with redirect_stdout(io.StringIO()) as f:
            run("+\n", io=IO())
        assert f.getvalue().strip() == "1 0"

    def test_invalid_jump_target(self) -> None:
        """Test program with invalid jump target (should not crash)."""
        with redirect_stdout(io.StringIO()) as f:
            run("~\n999", io=IO())
        assert f.getvalue().strip() == "0 0"

    def test_tilde_without_target_rejected(self) -> None:
        """A ~ with no matching jump-line number is malformed."""
        import pytest

        with pytest.raises(ValueError, match="jump target"):
            run("~~\n1", io=IO())

    def test_multiple_tildes(self) -> None:
        """Test program with multiple tildes and jump targets."""
        with redirect_stdout(io.StringIO()) as f:
            run("~+~+~\n3 2 1", io=IO())
        assert f.getvalue().strip() == "0 0"

    def test_register_overflow_simulation(self) -> None:
        """Test that registers can handle large values."""
        with redirect_stdout(io.StringIO()) as f:
            run("+" * 1000, io=IO())
        assert f.getvalue().strip() == "1000 0"


class TestMinskySwapExamples:
    """Test example programs and common patterns."""

    def test_hello_world_pattern(self) -> None:
        """Test a simple pattern that could be used for output."""
        with redirect_stdout(io.StringIO()) as f:
            run("+++*+++", io=IO())
        assert f.getvalue().strip() == "3 3"

    def test_register_copy_pattern(self) -> None:
        """Test copying value between registers."""
        with redirect_stdout(io.StringIO()) as f:
            run("+++*+++*~+~\n2 1", io=IO())
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
            run(program, io=IO())
        assert f.getvalue().strip() == "0 2"


class TestStepMachine:
    def test_the_register_dump_happens_once(self) -> None:
        """Stepping a halted machine again does not re-print the registers.

        ``step`` is called by the VM and by the cycle detector, either of
        which can run one past the end, so the dump is guarded by a flag
        rather than by the caller counting steps.
        """
        import io
        from contextlib import redirect_stdout

        from esolangs.interpreters.register_based.minsky_swap import _Machine

        machine = _Machine("+", IO())
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            while not machine.halted:
                machine.step()
            machine.step()  # the dump
            machine.step()  # once halted and dumped, a no-op
        assert buffer.getvalue().strip() == "1 0"

    def test_a_decrement_targeting_line_zero_falls_through(self) -> None:
        """A jump target of ``0`` is falsy, so ``~`` advances instead.

        Every ``~`` is given a target at parse time, so the branch cannot
        be reached by omitting one -- but a target of line 0 reads as
        false, and the cursor then moves on rather than jumping.  Whether
        that is the intended reading of line 0 is the language's question;
        this pins what the interpreter does with it.
        """
        from esolangs.interpreters.register_based.minsky_swap import _Machine

        machine = _Machine("~\n0", IO())  # zero register, target line 0
        machine.step()
        assert machine.reg == [0, 0], "nothing to decrement"
        assert machine.ind == 1, "the cursor advanced rather than jumping"


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.register_based.minsky_swap import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "+"
    halting_program = "+"
    looping_program = "~\n1"
