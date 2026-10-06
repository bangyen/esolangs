"""Unit tests for the BrainIf interpreter."""

from typing import ClassVar

import esolangs.debugger as debugger_api
from esolangs.interpreters.tape_based.brainif import run
from tests.interpreters.contract import (
    CycleContract,
    InputCursorContract,
    StateViewContract,
)
from tests.interpreters.runner import run_program
from tests.raises import raises_message


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


class TestBrainIfBasicCommands:
    def test_conditional_execution(self) -> None:
        # The output line is only executed when the cell holds 1
        assert run_and_capture(["if 1 output"]) == ""

    def test_input_preserves_newlines(self) -> None:
        """Input stores a newline rather than skipping it."""
        assert run_and_capture(["if 0 input", "if 10 output"], inputs=["", "A"]) == "\n"

    def test_move_left_of_cell_zero_is_a_fresh_zero_cell(self) -> None:
        code = ["if 0 increment", "if 1 left", "if 0 output", "if 1 output"]
        assert run_and_capture(code) == "\x00"

    def test_left_of_zero_and_back_keeps_both_cells(self) -> None:
        """The grown cell and the start cell are distinct, in both engines."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainif import _Machine

        code = [
            "if 0 increment",  # start cell -> 1
            "if 1 left",  # grow: a new cell 0
            "if 0 left",  # grow again
            "if 0 increment",
            "if 1 increment",  # leftmost -> 2
            "if 2 right",
            "if 0 right",  # back on the start cell
            "if 1 output",
        ]
        assert run_and_capture(code) == "\x01"
        machine = _Machine(code, ScriptedIO())
        while not machine.halted:
            machine.step()
        assert (machine.tape, machine.ptr) == ((2, 0, 1), 2)

    def test_a_write_keeps_the_cell_to_its_right(self) -> None:
        """Writing one cell rebuilds the tape around it, dropping nothing."""
        code = [
            "if 0 increment",  # cell 0 -> 1
            "if 1 right",  # to cell 1
            "if 0 increment",  # cell 1 -> 1
            "if 1 increment",  # cell 1 -> 2
            "if 2 left",  # back to cell 0
            "if 1 increment",  # cell 0 -> 2, rebuilding the tape around it
            "if 2 right",
            "if 2 output",  # cell 1 must still hold 2
        ]
        assert run_and_capture(code) == "\x02"

    def test_the_walk_out_and_back(self) -> None:
        """Walk out to cell 3 and back, marking each cell on the return."""
        code = [
            "if 0 right",  # cell 1
            "if 0 right",  # cell 2
            "if 0 right",  # cell 3
            "if 0 increment",  # cell 3 = 1
            "if 1 left",  # cell 2
            "if 0 increment",  # cell 2 = 1
            "if 1 left",  # cell 1
            "if 0 increment",  # cell 1 = 1
            "if 1 left",  # cell 0, untouched
            "if 0 output",
            "if 0 right",  # cell 1 again
            "if 1 output",
        ]
        assert run_and_capture(code) == "\x00\x01"


class TestBrainIfGeneratedHelloWorld:
    def test_long_climb_prints_two_characters(self) -> None:
        """A 107-line climb: one cell walked up to 72, printed, then to 105."""
        code = [f"if {n} increment" for n in range(72)]
        code.append("if 72 output")
        code += [f"if {n} increment" for n in range(72, 105)]
        code.append("if 105 output")
        assert run_and_capture(code) == "Hi"

    def test_truth_machine_zero(self) -> None:
        """A 0 input prints 0 and halts."""
        program = [
            "if 0 input",
            "if 48 output",
            "if 48 goto 6",
            "if 49 output",
            "if 49 goto 2",
        ]
        assert run_and_capture(program, inputs=["0"]) == "0"

    def test_unknown_instruction_rejected(self) -> None:
        import pytest

        for value in (0, 1):
            with pytest.raises(ValueError, match="unknown BrainIf command"):
                run_and_capture([f"if {value} frobnicate"])

    def test_embedded_command_names_do_not_execute(self) -> None:
        import pytest

        for command in ("incidental", "incrementoutput", "XinputY", "moveright"):
            with pytest.raises(ValueError, match="unknown BrainIf command"):
                run_and_capture([f"if 0 {command}", "if 0 output"])

    def test_missing_value_rejected(self) -> None:
        """A line without a value operand is malformed."""

        with raises_message(ValueError, "malformed BrainIf line: if"):
            run_and_capture(["if"])

    def test_a_value_with_no_command_is_rejected(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="unknown BrainIf command"):
            run_and_capture(["if 0", "if 0 output"])


class TestStepMachine:
    def test_step_tracks_cells_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainif import _Machine

        machine = _Machine(["if 0 increment", "if 1 output"], ScriptedIO())
        assert (machine.ind, machine.cells) == (0, (0,))
        machine.step()  # cell 0 is 0: increment
        assert machine.cells == (1,)
        machine.step()  # cell 1 is 1: output
        assert machine.io.getvalue() == "\x01"
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 2

    def test_machine_steps_over_a_blank_line(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainif import _Machine

        machine = _Machine(["", "if 0 output"], ScriptedIO())
        machine.step()
        assert machine.ind == 1

    def test_the_read_lands_in_the_cell(self) -> None:
        """``input`` puts the byte where the language says it goes."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainif import _Machine

        machine = _Machine(["if 0 input"], ScriptedIO("A"))
        machine.step()
        assert machine.cells == (ord("A"),)

    def test_goto_loop_is_detected_as_a_cycle(self) -> None:
        """A goto back to itself with the cell unchanged loops forever."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainif import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine(["if 0 goto 1"], ScriptedIO())) is False


def test_a_blank_line_is_skipped() -> None:
    """A line with nothing on it advances the counter and does no work."""
    assert run_and_capture(["if 0 increment", "", "if 1 output"]) == "\x01"
    assert run_and_capture(["if 0 increment", "", "   ", "if 1 output"]) == "\x01"


def test_run_reuses_a_parsed_line_after_a_backward_goto() -> None:
    code = ["if 1 increment", "if 0 increment", "if 1 goto 1"]
    assert run_and_capture(code) == ""


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.brainif import _Machine

    return _Machine(code, ScriptedIO())


def _reader(code: object, stdin: str) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.brainif import _Machine

    return _Machine(code, ScriptedIO(stdin))


class TestContract(CycleContract, InputCursorContract, StateViewContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    reader = staticmethod(_reader)
    reading_program: ClassVar[list[str]] = ["if 0 input"]
    reading_stdin = "A"
    halting_program: ClassVar[list[str]] = ["if 0 output"]
    looping_program: ClassVar[list[str]] = ["if 0 goto 1"]
    state_views: ClassVar[tuple[str, ...]] = ("ptr", "ip", "memory")
    viewing_program: ClassVar[list[str]] = ["if 0 right", "if 0 output"]


def test_malformed_command_lines_are_rejected() -> None:
    import pytest

    for line in (
        "garbage 0 output",
        "if 0 output junk",
        "if 0 frobnicate output",
        "if 0 goto 1 junk",
        "if 0 move up",
        "if 0 move right junk",
    ):
        with pytest.raises(ValueError, match="malformed BrainIf line"):
            run_and_capture([line])


def test_canonical_move_commands_remain_valid() -> None:
    assert (
        run_and_capture(
            [
                "if 0 increment",
                "if 1 move right",
                "if 0 output",
                "if 0 move left",
                "if 1 output",
            ]
        )
        == "\x00\x01"
    )


def test_nonpositive_goto_targets_are_rejected_by_run_and_vm() -> None:
    import pytest

    import esolangs

    for target in (0, -1):
        for guard in (0, 1):
            code = f"if {guard} goto {target}"
            with pytest.raises(esolangs.ProgramError, match="positive line number"):
                esolangs.run("BrainIf", code)
            vm = debugger_api.make_vm("BrainIf", code)
            with pytest.raises(esolangs.ProgramError, match="positive line number"):
                vm.step()


def test_positive_goto_targets_match_run_and_vm() -> None:
    import esolangs
    from esolangs.vm import run_until_halt

    for code, expected in (
        ("if 0 goto 3\nif 0 output\nif 0 increment\nif 1 output", "\x01"),
        ("if 0 goto 2", ""),
    ):
        assert esolangs.run("BrainIf", code) == expected
        vm = debugger_api.make_vm("BrainIf", code)
        assert run_until_halt(vm, limit=4)
        assert vm.output == expected


def test_a_condition_past_the_int_str_digit_cap_parses() -> None:
    """Pins parse_integer: a 5001-digit condition used to raise."""
    big = "1" + "0" * 5000
    assert run_and_capture([f"if {big} output", "if 0 output"]) == "\x00"


def test_goto_without_a_target_is_rejected() -> None:
    import pytest

    with pytest.raises(ValueError, match="goto requires a target line"):
        run_and_capture(["if 0 goto"])


def test_moving_right_over_an_existing_cell_does_not_grow_the_tape() -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.brainif import _Machine

    machine = _Machine(["if 0 right", "if 0 left", "if 0 right"], ScriptedIO())
    for _ in range(3):
        machine.step()
    assert (machine.ptr, machine.cells) == (1, (0, 0))
