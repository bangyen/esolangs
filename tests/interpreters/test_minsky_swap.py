r"""Unit tests for Minsky Swap interpreter."""

import io
from contextlib import redirect_stdout

from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.minsky_swap import run
from tests.interpreters.contract import (
    CycleContract,
    SnapshotContract,
    StateViewContract,
)
from tests.raises import raises_message


class TestMinskySwapBasicCommands:
    r"""Test basic Minsky Swap command functionality."""

    def test_increment_command(self) -> None:
        r"""Test + command increments the current register."""
        with redirect_stdout(io.StringIO()) as f:
            run("+", io=IO())
        assert f.getvalue().strip() == "1 0"

        with redirect_stdout(io.StringIO()) as f:
            run("++", io=IO())
        assert f.getvalue().strip() == "2 0"

    def test_swap_command(self) -> None:
        r"""Test * command swaps the register pointer."""
        with redirect_stdout(io.StringIO()) as f:
            run("*+", io=IO())
        assert f.getvalue().strip() == "0 1"

        with redirect_stdout(io.StringIO()) as f:
            run("+*+", io=IO())
        assert f.getvalue().strip() == "1 1"

    def test_decrement_jump_command(self) -> None:
        r"""Test ~ command decrements if nonzero, jumps if zero."""
        with redirect_stdout(io.StringIO()) as f:
            run("+~\n1", io=IO())
        assert f.getvalue().strip() == "0 0"

        with redirect_stdout(io.StringIO()) as f:
            run("~+\n2", io=IO())
        # ~ jumps to command 2 (the +).
        assert f.getvalue().strip() == "1 0"

    def test_jump_targets(self) -> None:
        r"""Test jump targets from the jump line."""
        with redirect_stdout(io.StringIO()) as f:
            run("~+~\n2 1", io=IO())
        assert f.getvalue().strip() == "0 0"

    def test_empty_program(self) -> None:
        r"""Test empty program outputs zeros."""
        with redirect_stdout(io.StringIO()) as f:
            run("", io=IO())
        assert f.getvalue().strip() == "0 0"

    def test_whitespace_ignored(self) -> None:
        r"""Test that whitespace and non-command characters are ignored."""
        with redirect_stdout(io.StringIO()) as f:
            run("  +  \n  ", io=IO())
        assert f.getvalue().strip() == "1 0"

    def test_stripped_characters_do_not_shift_the_jump_targets(self) -> None:
        r"""Padding is removed, rather than replaced with something inert."""
        with redirect_stdout(io.StringIO()) as f:
            run(" ~++\n3", io=IO())
        assert f.getvalue().strip() == "1 0"


class TestMinskySwapReadableNotation:
    r"""Test readable Minsky Swap notation (RMSN)."""

    def test_inc_command(self) -> None:
        r"""Test inc() command in readable notation."""
        with redirect_stdout(io.StringIO()) as f:
            run("inc();", io=IO())
        assert f.getvalue().strip() == "1 0"

        with redirect_stdout(io.StringIO()) as f:
            run("inc(); inc();", io=IO())
        assert f.getvalue().strip() == "2 0"

    def test_swap_command_readable(self) -> None:
        r"""Test swap() command in readable notation."""
        with redirect_stdout(io.StringIO()) as f:
            run("swap(); inc();", io=IO())
        assert f.getvalue().strip() == "0 1"

    def test_decnz_command(self) -> None:
        r"""Test decnz() command in readable notation."""
        with redirect_stdout(io.StringIO()) as f:
            run("inc(); decnz(1);", io=IO())
        assert f.getvalue().strip() == "0 0"

        with redirect_stdout(io.StringIO()) as f:
            run("decnz(2); inc();", io=IO())
        assert f.getvalue().strip() == "1 0"

    def test_mixed_notation(self) -> None:
        r"""Test mixing compact and readable notation."""
        with redirect_stdout(io.StringIO()) as f:
            run("inc(); +", io=IO())
        assert f.getvalue().strip() == "2 0"

    def test_a_readable_command_contributes_exactly_one_symbol(self) -> None:
        r"""Each ``inc()``/``swap()`` becomes one command, not a run of them."""
        with redirect_stdout(io.StringIO()) as f:
            run("decnz(5); inc(); swap(); inc(); inc();", io=IO())
        assert f.getvalue().strip() == "1 0"

    def test_a_bare_decnz_jumps_to_the_first_line(self) -> None:
        r"""``decnz();`` with no argument targets line 1."""
        from esolangs.interpreters.register_based.minsky_swap import _Machine

        machine = _Machine("decnz();", IO())
        machine.step()  # zero register, so the tilde.
        assert machine.ind == 0, "the jump returned to the first command"
        assert not machine.halted

    def test_a_readable_command_is_stripped_with_its_argument(self) -> None:
        r"""The cleanup removes the whole ``name(...)``, parentheses included."""
        with redirect_stdout(io.StringIO()) as f:
            run("inc(1+2); inc();", io=IO())
        assert f.getvalue().strip() == "1 0"

    def test_the_compact_tail_keeps_only_its_commands(self) -> None:
        r"""Spaces in the trailing compact part are dropped, not kept."""
        with redirect_stdout(io.StringIO()) as f:
            run("decnz(3); + +", io=IO())
        assert f.getvalue().strip() == "1 0"


class TestMinskySwapProgramFlow:
    r"""Test program flow control and complex programs."""

    def test_simple_loop(self) -> None:
        r"""Test a simple counting loop."""
        with redirect_stdout(io.StringIO()) as f:
            run("+++~\n1", io=IO())
        assert f.getvalue().strip() == "2 0"

    def test_register_swapping_loop(self) -> None:
        r"""Test program that swaps between registers."""
        with redirect_stdout(io.StringIO()) as f:
            run("+*+*+", io=IO())
        assert f.getvalue().strip() == "2 1"

    def test_conditional_jump(self) -> None:
        r"""Test conditional jump based on register value."""
        with redirect_stdout(io.StringIO()) as f:
            run("++~+~\n2 1", io=IO())
        assert f.getvalue().strip() == "1 0"

    def test_complex_program(self) -> None:
        r"""Test a more complex program with multiple operations."""
        with redirect_stdout(io.StringIO()) as f:
            run("++*++*+++", io=IO())
        assert f.getvalue().strip() == "5 2"


class TestMinskySwapEdgeCases:
    r"""Test edge cases and error conditions."""

    def test_empty_jump_line(self) -> None:
        r"""Test program with empty jump line."""
        with redirect_stdout(io.StringIO()) as f:
            run("+\n", io=IO())
        assert f.getvalue().strip() == "1 0"

    def test_invalid_jump_target(self) -> None:
        r"""Test program with invalid jump target (should not crash)."""
        with redirect_stdout(io.StringIO()) as f:
            run("~\n999", io=IO())
        assert f.getvalue().strip() == "0 0"

    def test_tilde_without_target_rejected(self) -> None:
        r"""A ~ with no matching jump-line number is malformed."""
        with raises_message(ValueError, "unmatched '~' with no jump target"):
            run("~~\n1", io=IO())

    def test_multiple_tildes(self) -> None:
        r"""Test program with multiple tildes and jump targets."""
        with redirect_stdout(io.StringIO()) as f:
            run("~+~+~\n3 2 1", io=IO())
        assert f.getvalue().strip() == "0 0"

    def test_register_overflow_simulation(self) -> None:
        r"""Test that registers can handle large values."""
        with redirect_stdout(io.StringIO()) as f:
            run("+" * 1000, io=IO())
        assert f.getvalue().strip() == "1000 0"


class TestMinskySwapExamples:
    r"""Test example programs and common patterns."""

    def test_hello_world_pattern(self) -> None:
        r"""Test a simple pattern that could be used for output."""
        with redirect_stdout(io.StringIO()) as f:
            run("+++*+++", io=IO())
        assert f.getvalue().strip() == "3 3"

    def test_register_copy_pattern(self) -> None:
        r"""Test copying value between registers."""
        with redirect_stdout(io.StringIO()) as f:
            run("+++*+++*~+~\n2 1", io=IO())
        assert f.getvalue().strip() == "2 3"

    def test_readable_notation_example(self) -> None:
        r"""Test a complete readable notation example."""
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
        r"""Stepping a halted machine again does not re-print the registers."""
        import io
        from contextlib import redirect_stdout

        from esolangs.interpreters.register_based.minsky_swap import _Machine

        machine = _Machine("+", IO())
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            while not machine.halted:
                machine.step()
            machine.step()  # the dump.
            machine.step()  # once halted and dumped, a.
        assert buffer.getvalue().strip() == "1 0"

    def test_a_decrement_targeting_line_zero_falls_through(self) -> None:
        r"""A jump target of ``0`` is falsy, so ``~`` advances instead."""
        from esolangs.interpreters.register_based.minsky_swap import _Machine

        machine = _Machine("~\n0", IO())  # zero register, target line 0.
        machine.step()
        assert machine.reg == (0, 0), "nothing to decrement"
        assert machine.ind == 1, "the cursor advanced rather than jumping"


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.register_based.minsky_swap import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract, CycleContract, StateViewContract):
    r"""The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "+"
    halting_program = "+"
    looping_program = "~\n1"
    # `dumped` only flips on the.
    # prints its registers, so the.
    # It is still read either side,.
    # `reg` and `ip` are what move.
    state_views = ("ptr", "reg", "dumped", "ip", "memory")
    # `*` swaps the register pair,.
    # register.
    # check does not take.
    viewing_program = "*+"
    constant_views = frozenset({"dumped"})


class TestStateViewValues:
    r"""The named views read the slots they claim, not one another."""

    def test_ptr_is_the_register_pointer_not_the_cursor(self) -> None:
        r"""The swap moves the pointer once; the cursor moves every step."""
        machine = _machine("*+")
        while not machine.halted:
            machine.step()
        assert machine.ptr == 1
        assert machine.ip == 2
