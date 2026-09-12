r"""Unit tests for the Suffolk interpreter."""

import io
from contextlib import redirect_stdout

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.suffolk import run


def run_and_capture(code: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, io=IO())
    return buffer.getvalue()


class TestSuffolk:
    def test_count_and_output(self) -> None:
        r"""66 increments of the counter then a print yields 'A'."""
        assert run_and_capture("!" * 66 + "<.") == "A"

    def test_other_value(self) -> None:
        assert run_and_capture("!" * 70 + "<.") == "E"

    def test_output_requires_accumulator(self) -> None:
        r"""A ."""
        assert run_and_capture("!.<<!") == ""

    def test_no_halt_without_instruction(self) -> None:
        r"""A program that writes nothing still ends, and prints nothing."""
        assert run_and_capture("!!!!<<!") == ""

    def test_move_right(self) -> None:
        r"""> moves the pointer to a new tape cell."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.suffolk import _Machine

        program = "!!!!!!!!>!><<<<<<<<<.!"
        machine = _Machine(program, ScriptedIO())
        for _ in range(len(program)):
            machine.step()
        assert machine.io.getvalue() == "@"

    def test_input(self) -> None:
        r""", reads input into the accumulator."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine(",.", ScriptedIO("B\n"))
        machine.step()
        machine.step()
        assert machine.io.getvalue() == "A"

    def test_empty_program_rejected(self) -> None:
        r"""An empty program is malformed."""
        import pytest

        with pytest.raises(ValueError, match=r"^Suffolk program cannot be empty$"):
            run("", IO())

    def test_a_repeated_state_ends_the_run(self) -> None:
        r"""``run`` stops on a proof, not a count."""
        assert run_and_capture("!<.<<!") == "\x00"

    def test_pointer_walks_past_the_second_cell(self) -> None:
        r"""Consecutive > keep incrementing the pointer, they do not set it."""
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine(">>>!", IO())
        for expected in (0, 1, 2, 3):
            assert machine.ptr == expected
            machine.step()
        assert machine.tape == (0, 0, 0, 1)

    def test_cell_clamps_at_zero(self) -> None:
        r"""."""
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine("!!!<>!", IO())
        for _ in range(6):
            machine.step()
        assert machine.tape == (3, 0)

    def test_accumulator_is_subtracted_at_the_cell(self) -> None:
        r"""."""
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine("!!<!", IO())
        for _ in range(4):
            machine.step()
        assert machine.tape == (1,)

    def test_empty_input_clears_the_accumulator(self) -> None:
        r""", on an empty line leaves the accumulator at zero, not one."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine(",.", ScriptedIO("\n"))
        machine.step()
        assert machine.acc == 0


class TestStepMachine:
    def test_snapshot_changes_after_a_step(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine("!", IO())
        before = machine.snapshot()
        machine.step()  # .
        assert machine.snapshot() != before
        assert machine.tape == (1,)

    def test_halted_is_always_false(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine(".", IO())
        assert machine.halted is False
        for _ in range(5):
            machine.step()
        assert machine.halted is False

    def test_step_wraps_at_code_end(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine("!.", IO())
        machine.step()  # .
        assert machine.ind == 1
        assert machine.tape == (1,)
        machine.step()  # .
        assert machine.ind == 0  # wrapped past the last.

    def test_cycle_is_detected(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # "." never changes state, so.
        assert run_until_halt_or_cycle(_Machine(".", IO())) is False
        assert run_until_halt_or_cycle(_Machine("<", IO())) is False

    def test_snapshot_includes_the_input_cursor(self) -> None:
        r"""Reading a byte changes the state, even when nothing else does."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine(",", ScriptedIO("\x00\n\x00\n"))
        before = machine.snapshot()
        machine.step()  # consumes a line; acc stays 0.
        assert machine.acc == before[2]  # nothing else moved.
        assert machine.snapshot() != before

    def test_a_program_that_reads_is_not_called_periodic(self) -> None:
        r"""A read one byte from EOF must not be reported as a hang."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.suffolk import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine(",.", ScriptedIO("A\n"))
        assert run_until_halt_or_cycle(machine) is True
        assert machine.halted

    def test_snapshot_excludes_pass_count(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine

        # "." is a no-op when acc is 0,.
        # (len(code) steps) equals the.
        # not be part of snapshot, or.
        # cycle detector would never.
        machine = _Machine("..", IO())
        before = machine.snapshot()
        machine.step()
        machine.step()  # one whole pass.
        assert machine.snapshot() == before
