r"""Unit tests for the BrainIf interpreter."""

from typing import ClassVar

from esolangs.interpreters.tape_based.brainif import run
from tests.interpreters.contract import (
    CycleContract,
    InputCursorContract,
    StateViewContract,
)
from tests.interpreters.runner import run_program


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


class TestBrainIfBasicCommands:
    def test_increment(self) -> None:
        assert run_and_capture(["if 0 increment", "if 1 output"]) == "\x01"

    def test_output_zero(self) -> None:
        assert run_and_capture(["if 0 output"]) == "\x00"

    def test_conditional_execution(self) -> None:
        # The output line is only.
        assert run_and_capture(["if 1 output"]) == ""

    def test_input(self) -> None:
        assert run_and_capture(["if 0 input", "if 65 output"], inputs=["A"]) == "A"

    def test_input_retries_past_blank_lines(self) -> None:
        r"""A blank line is read again, not stored as the newline it ended."""
        code = ["if 0 input", "if 65 output"]
        assert run_and_capture(code, inputs=["", "", "A"]) == "A"

    def test_move_right(self) -> None:
        code = ["if 0 right", "if 0 increment", "if 1 output"]
        assert run_and_capture(code) == "\x01"

    def test_move_left_clamps_at_zero(self) -> None:
        code = ["if 0 left", "if 0 increment", "if 1 output"]
        assert run_and_capture(code) == "\x01"

    def test_a_write_keeps_the_cell_to_its_right(self) -> None:
        r"""Writing one cell rebuilds the tape around it, dropping nothing."""
        code = [
            "if 0 increment",  # cell 0 -> 1.
            "if 1 right",  # to cell 1.
            "if 0 increment",  # cell 1 -> 1.
            "if 1 increment",  # cell 1 -> 2.
            "if 2 left",  # back to cell 0.
            "if 1 increment",  # cell 0 -> 2, rebuilding the.
            "if 2 right",
            "if 2 output",  # cell 1 must still hold 2.
        ]
        assert run_and_capture(code) == "\x02"

    def test_the_walk_out_and_back(self) -> None:
        r"""Walk out to cell 3 and back, marking each cell on the return."""
        code = [
            "if 0 right",  # cell 1.
            "if 0 right",  # cell 2.
            "if 0 right",  # cell 3.
            "if 0 increment",  # cell 3 = 1.
            "if 1 left",  # cell 2.
            "if 0 increment",  # cell 2 = 1.
            "if 1 left",  # cell 1.
            "if 0 increment",  # cell 1 = 1.
            "if 1 left",  # cell 0, untouched.
            "if 0 output",
            "if 0 right",  # cell 1 again.
            "if 1 output",
        ]
        assert run_and_capture(code) == "\x00\x01"

    def test_a_new_cell_starts_at_zero(self) -> None:
        r"""Moving right onto fresh tape appends a zero, not a one."""
        assert run_and_capture(["if 0 right", "if 0 output"]) == "\x00"


class TestBrainIfGeneratedHelloWorld:
    def test_long_climb_prints_two_characters(self) -> None:
        r"""A 107-line climb: one cell walked up to 72, printed, then to 105."""
        code = [f"if {n} increment" for n in range(72)]
        code.append("if 72 output")
        code += [f"if {n} increment" for n in range(72, 105)]
        code.append("if 105 output")
        assert run_and_capture(code) == "Hi"

    def test_truth_machine_zero(self) -> None:
        r"""A 0 input prints 0 and halts."""
        program = [
            "if 0 input",
            "if 48 output",
            "if 48 goto 6",
            "if 49 output",
            "if 49 goto 2",
        ]
        assert run_and_capture(program, inputs=["0"]) == "0"

    def test_unknown_instruction_ignored(self) -> None:
        r"""Lines without a recognized instruction are ignored."""
        assert run_and_capture(["if 0 output", "if 0 frobnicate"]) == "\x00"

    def test_goto(self) -> None:
        r"""Goto jumps to the given line number."""
        code = ["if 0 goto 3", "if 0 output", "if 0 increment", "if 1 output"]
        assert run_and_capture(code) == "\x01"

    def test_missing_value_rejected(self) -> None:
        r"""A line without a value operand is malformed."""
        import pytest

        with pytest.raises(ValueError, match=r"^malformed BrainIf line: if$"):
            run_and_capture(["if"])

    def test_a_value_with_no_command_is_well_formed(self) -> None:
        r"""Two tokens are enough: ``if 0`` names a value and does nothing."""
        assert run_and_capture(["if 0", "if 0 output"]) == "\x00"

    def test_goto_missing_target_rejected(self) -> None:
        r"""A goto without a target line is malformed."""
        import pytest

        with pytest.raises(ValueError, match=r"^goto requires a target line$"):
            run_and_capture(["if 0 goto"])


class TestStepMachine:
    def test_step_tracks_cells_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainif import _Machine

        machine = _Machine(["if 0 increment", "if 1 output"], ScriptedIO())
        assert (machine.ind, machine.cells) == (0, (0,))
        machine.step()  # cell 0 is 0: increment.
        assert machine.cells == (1,)
        machine.step()  # cell 1 is 1: output.
        assert machine.io.getvalue() == "\x01"
        assert machine.halted
        machine.step()  # stepping a halted machine is.
        assert machine.ind == 2

    def test_the_read_lands_in_the_cell(self) -> None:
        r"""``input`` puts the byte where the language says it goes."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainif import _Machine

        machine = _Machine(["if 0 input"], ScriptedIO("A"))
        machine.step()
        assert machine.cells == (ord("A"),)

    def test_goto_loop_is_detected_as_a_cycle(self) -> None:
        r"""A goto back to itself with the cell unchanged loops forever."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainif import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine(["if 0 goto 1"], ScriptedIO())) is False


def test_a_blank_line_is_skipped() -> None:
    r"""A line with nothing on it advances the counter and does no work."""
    assert run_and_capture(["if 0 increment", "", "if 1 output"]) == "\x01"
    assert run_and_capture(["if 0 increment", "", "   ", "if 1 output"]) == "\x01"


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.brainif import _Machine

    return _Machine(code, ScriptedIO())


def _reader(code: object, stdin: str) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.brainif import _Machine

    return _Machine(code, ScriptedIO(stdin))


class TestContract(CycleContract, InputCursorContract, StateViewContract):
    r"""The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    reader = staticmethod(_reader)
    reading_program: ClassVar[list[str]] = ["if 0 input"]
    reading_stdin = "A"
    halting_program: ClassVar[list[str]] = ["if 0 output"]
    looping_program: ClassVar[list[str]] = ["if 0 goto 1"]
    state_views: ClassVar[tuple[str, ...]] = ("ptr", "ip", "memory")
    viewing_program: ClassVar[list[str]] = ["if 0 right", "if 0 output"]
