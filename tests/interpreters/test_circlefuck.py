"""Unit tests for the Circlefuck interpreter."""

import pytest

from esolangs.interpreters.tape_based.circlefuck import parse, run
from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.interpreters.runner import run_program
from tests.raises import raises_message


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


class TestCirclefuck:
    def test_hello_world(self) -> None:
        """Canonical Hello, World! program from esolangs.org."""
        program = "<[.<]@\\0\\n!dlroW\\ ,olleH"
        assert run_and_capture(program) == "Hello, World!\n"

    def test_truth_machine_zero(self) -> None:
        """A 0 input prints 0 and halts."""
        program = "," + "-" * 48 + "[[-]" + "+" * 49 + ".]" + "+" * 48 + ".@"
        assert run_and_capture(program, inputs=["0"]) == "0"

    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            pytest.param("++@", "", id="halt"),
            # . outputs the cell under the data pointer (self-modified).
            pytest.param("+.@", ",", id="output_cell_value"),
            # # steps over the next cell and no further.
            pytest.param("#..@", "#", id="skip_passes_over_exactly_one_instruction"),
            # 255 + 1 comes back to zero, which no smaller cell can show.
            pytest.param(
                "\\xFF+.@", "\x00", id="increment_wraps_at_two_hundred_fifty_six"
            ),
            # 0 - 1 comes back as 255, the other end of the same wrap.
            pytest.param("\\0-.@", "\xff", id="decrement_wraps_at_zero"),
            # Only ``[`` and ``]`` jump; every other letter is inert.
            pytest.param("+X@", "", id="a_letter_is_not_a_bracket"),
            pytest.param(",@", "", id="exhausted_input_is_a_no_op"),
            # { inserts a new zero cell before the current one.
            pytest.param("{+.@", "\x01", id="insert_cell"),
            # } deletes the current cell.
            pytest.param("+}.@", "}", id="delete_cell"),
        ],
    )
    def test_result(self, code, expected) -> None:
        assert run_and_capture(code) == expected

    def test_an_input_character_above_255_is_taken_modulo_256(self) -> None:
        """``,`` writes a cell, so it reduces exactly as ``+`` and ``-`` do."""
        assert run_and_capture(",.@", inputs=["Ā"]) == "\x00"
        assert run_and_capture(",.@", inputs=["ā"]) == "\x01"
        assert run_and_capture(",+.@", inputs=["Ā"]) == "\x01"


class TestStepMachine:
    def test_step_tracks_cells_and_pointers(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.circlefuck import _Machine

        machine = _Machine("+.@", ScriptedIO())
        assert (machine.ind, machine.ptr, machine.cells) == (0, 0, (43, 46, 64))
        machine.step()  # + sets the cell
        assert machine.cells == (44, 46, 64)
        machine.step()  # . prints it
        assert machine.io.getvalue() == ","
        machine.step()  # @ halts
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 2

    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            # :math:`\NNN` escape sequences decode to a single byte.
            pytest.param("\\065.@", "A", id="decimal_escape"),
            pytest.param("\\x41.@", "A", id="hex_escape"),
            # A lone ``\F`` is a hex digit; the lowercase run is not one.
            pytest.param("\\F.@", "\x0f", id="bare_hex_digit_escape_is_uppercase"),
            # ``\o101`` names the same octal byte as ``\101``.
            pytest.param("\\o101.@", "A", id="a_leading_o_is_dropped_from_an_escape"),
            # ``\065`` reads the same whichever digit the decode starts at.
            pytest.param(
                "\\165.@", "\xa5", id="decimal_escape_keeps_its_leading_digit"
            ),
            # Cells below the space are stripped, so only the ``.`` remains.
            pytest.param("\x1f.@", ".", id="the_unit_separator_is_not_a_command"),
            # 127 is stripped too, so the printable range is open at both ends.
            pytest.param("\x7f.@", ".", id="delete_is_not_a_command"),
            # ``[`` on a zero cell jumps to its own ``]``, not a bracket behind it.
            pytest.param(
                "\\0[.].[.]@", "\x00", id="a_skipped_loop_scans_forward_for_its_partner"
            ),
            pytest.param("\\n.@", "\n", id="newline_escape"),
        ],
    )
    def test_result(self, code, expected) -> None:
        assert run_and_capture(code) == expected

    def test_named_space_and_invalid_escapes(self) -> None:
        assert parse("\\space") == [32]
        assert parse("\\\\") == [92]
        for source in ("\\", "\\q", "\\o89", "\\xg0", "\\999"):
            with pytest.raises(ValueError, match="invalid Circlefuck escape"):
                parse(source)

    def test_unmatched_taken_brackets_suspend(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.circlefuck import _Machine

        for code in ("\\0[.@", "]@"):
            machine = _Machine(code, ScriptedIO())
            if code.startswith("\\0"):
                machine.step()
            before = machine.snapshot()
            for _ in range(3):
                machine.step()
                assert machine.snapshot() == before
                assert not machine.halted
            assert machine.io.getvalue() == ""

    def test_the_empty_program_message_reads_exactly(self) -> None:
        """``match=`` only looks for a substring, so pin the whole message."""
        with raises_message(ValueError, "Circlefuck program cannot be empty"):
            run_and_capture("")

    def test_insert_leaves_the_cursor_on_the_cell_after_the_new_one(self) -> None:
        """``{`` steps the cursor past the cell it just pushed forward."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.circlefuck import _Machine

        machine = _Machine("+{+.@", ScriptedIO())
        machine.step()  # + raises cell 0
        machine.step()  # { inserts a zero before it and steps past both
        assert machine.ind == 3
        assert machine.cells == (0, 44, 123, 43, 46, 64)

    def test_edits_keep_the_instruction_successor(self) -> None:
        """Edits shift the instruction cursor before its normal advance."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.circlefuck import _Machine

        machine = _Machine("<{abc@", ScriptedIO())
        machine.step()
        machine.step()
        assert machine.ind == 2
        assert machine.cells == (60, 123, 97, 98, 99, 0, 64)

        machine = _Machine(">x}ab@", ScriptedIO())
        machine.step()
        machine.step()
        machine.step()
        assert machine.ind == 2
        assert machine.cells == (62, 125, 97, 98, 64)

    def test_state_reports_the_fields_and_copies_the_tape(self) -> None:
        """``state`` is an observer, so it must not alias the live tape."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.circlefuck import _Machine

        machine = _Machine("+.@", ScriptedIO())
        before = machine.state
        assert before == (0, 0, (43, 46, 64), False)

        machine.step()  # + raises cell 0 from 43 to 44
        assert machine.state == (1, 0, (44, 46, 64), False)
        # The earlier reading is a copy, so the write did not reach it.
        assert before == (0, 0, (43, 46, 64), False)

    def test_delete_last_cell_halts(self) -> None:
        """Deleting the last cell is an invalid operation."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture("}")
        # a pop that would leave the pointer out of bounds wraps instead of
        # leaking an IndexError
        with pytest.raises(HaltError):
            run_and_capture("<}}@")


def _machine(code: str) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.circlefuck import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes. ``><`` orbits the pointer forever; ``+.@`` halts."""

    machine = staticmethod(_machine)
    stepping_program = "><"
    halting_program = "+.@"
    looping_program = "><"


def test_an_octal_escape_above_377_is_rejected() -> None:
    """Pins the wiki's octal range 000-377: ``\\o400`` is not a byte."""
    assert parse("\\o377@") == [255, ord("@")]
    with pytest.raises(ValueError, match="invalid Circlefuck escape"):
        parse("\\o400@")


def test_a_decimal_escape_takes_ascii_digits_only() -> None:
    """Pins the wiki's "digits 0-9": Arabic-Indic digits are no escape."""
    with pytest.raises(ValueError, match="invalid Circlefuck escape"):
        parse("\\\u0661\u0662\u0663@")


def test_halting_on_at_changes_the_snapshot() -> None:
    """Pins ``done`` in the snapshot: ``@`` changes nothing else."""
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.circlefuck import _Machine

    machine = _Machine("@", ScriptedIO(""))
    before = machine.snapshot()
    machine.step()
    assert machine.halted
    assert machine.snapshot() != before
