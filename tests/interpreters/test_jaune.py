"""Unit tests for the Jaune interpreter."""

from functools import partial

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.jaune import run
from tests.interpreters import runner
from tests.interpreters.contract import SnapshotContract

run_program = partial(runner.run_program, run, suppress_eof=False)


class TestArithmetic:
    def test_add_and_output(self) -> None:
        assert run_program("6+5+^.") == "11"

    def test_explicit_zero_and_signed_counts_are_literals(self) -> None:
        assert run_program("0+^.") == "0"
        assert run_program("-2+^.") == "-2"
        assert run_program("+2+^.") == "2"
        assert run_program("5+-2-^.") == "7"
        with pytest.raises(HaltError, match="undefined label -1"):
            run_program("-1?")


class TestInput:
    def test_read_digit(self) -> None:
        assert run_program("v^.", "7\n") == "7"

    def test_input_eof(self) -> None:
        with pytest.raises(EOFError):
            run_program("v.", "")

    def test_numeric_input_accepts_whitespace_and_signs(self) -> None:
        """Numeric reads skip whitespace before the next integer."""
        assert run_program("v^.", "\n42") == "42"
        assert run_program("v^.", "-7") == "-7"


class TestMemory:
    def test_left_of_cell_zero_is_a_fresh_zero_cell(self) -> None:
        """``<`` at cell 0 grows the tape left onto a new zero cell."""
        assert run_program("5+<^.") == "0"
        assert run_program("5+<<<^.") == "0"

    def test_left_of_zero_and_back_keeps_both_cells(self) -> None:
        """The grown cell and the start cell are distinct and both kept."""
        assert run_program("5+<3+>^.") == "5"
        assert run_program("5+<3+>^<^.") == "53"
        assert run_program("5+<<>>^.") == "5"

    def test_the_hold_cell_starts_at_zero(self) -> None:
        """``&`` before any ``#`` adds nothing."""
        assert run_program("&^.") == "0"


class TestControlFlow:
    def test_loop_adder(self) -> None:
        # v+>v+1:1-<1+>1?<^. : read a, b; while b: b--, a++; print a
        assert run_program("v+>v+1:1-<1+>1?<^", "3\n4\n") == "7"

    def test_jump_on_nonzero(self) -> None:
        # 1+ sets cell to 1; 1? jumps to label 1 when nonzero
        assert run_program("1+1?2:^1:^.") == "1"

    def test_jump_on_zero(self) -> None:
        # cell is 0; 1! jumps to label 1 when zero
        assert run_program("1!1:^.") == "0"

    def test_subroutine(self) -> None:
        # v+>v+1@^.1$#<&; : read a, b; subroutine 1 adds hold to a; print
        assert run_program("v+>v+1@^.1$#<&;", "3\n4\n") == "7"

    def test_a_return_ends_only_itself(self) -> None:
        """``;`` consumes one character, leaving the next definition whole."""
        # call 1 then 2; subroutine 1 adds 5, subroutine 2 adds 3
        assert run_program("1@2@^.1$5+;2$3+;") == "8"


class TestComputedDispatch:
    """``v`` as the operand of a jump or a call."""

    def test_the_input_names_the_subroutine(self) -> None:
        assert run_program("v@^.1$5+;2$3+;", "1\n") == "5"
        assert run_program("v@^.1$5+;2$3+;", "2\n") == "3"

    def test_jump_on_nonzero_to_the_named_label(self) -> None:
        assert run_program("+v?%^.3:7+^.", "3\n") == "8"

    def test_a_read_operand_is_consumed_when_the_branch_is_not_taken(
        self,
    ) -> None:
        """The number is evaluated to have a command at all."""
        assert run_program("v?v^.3:", "3\n8\n") == "8"
        assert run_program("+v!v^.3:", "3\n8\n") == "8"

    def test_an_undefined_named_target_halts(self) -> None:
        with pytest.raises(HaltError, match="undefined subroutine 7"):
            run_program("v@^.1$5+;", "7\n")
        with pytest.raises(HaltError, match="undefined label 4"):
            run_program("v?^.1:9+;", "4\n")

    def test_the_target_is_looked_up_before_the_branch_is_tested(self) -> None:
        """An undefined label halts even when the jump would not be taken."""
        with pytest.raises(HaltError, match="undefined label 1"):
            run_program("v?^.9:", "1\n")

    def test_a_read_marker_defines_nothing(self) -> None:
        """``v:`` and ``v$`` are grammatical but have no findable identity."""
        from esolangs.interpreters.tape_based.jaune import _parse

        assert [c.op for c in _parse("v:5+")] == ["+"]
        assert [c.op for c in _parse("v$5+")] == ["+"]
        assert run_program("v:5+^.") == "5"
        assert run_program("v$5+^.") == "5"

    def test_a_loop_reading_its_own_target_exhausts_its_input(self) -> None:
        """Each pass of the loop reads again, so input decides the end."""
        with pytest.raises(EOFError):
            run_program("5+1:v?^.", "1\n1\n1\n")


class TestParsing:
    def test_an_uppercase_letter_is_no_more_a_command_than_a_lowercase_one(
        self,
    ) -> None:
        """``X`` is ignored, as every unrecognized character is."""
        assert run_program("X^.") == "0"
        assert run_program("1X^.") == "0"

    def test_bare_operator_requires_a_number(self) -> None:
        with pytest.raises(ValueError, match="requires a number"):
            run_program("?")

    def test_bare_operator_hint_puts_the_number_first(self) -> None:
        """The count precedes its command (``9:``), whatever the hint said."""
        with pytest.raises(ValueError, match="requires a number") as caught:
            run_program(":")
        assert any(
            "immediately before the command" in note for note in caught.value.__notes__
        )

    def test_runs_of_an_operator_carry_their_length(self) -> None:
        """``++`` is one command repeated twice, not two commands."""
        from esolangs.interpreters.tape_based.jaune import _parse

        assert [(c.op, c.arg) for c in _parse("+++")] == [("+", 3)]
        assert [(c.op, c.arg) for c in _parse("--")] == [("-", 2)]
        assert [(c.op, c.arg) for c in _parse("++-")] == [("+", 2), ("-", 1)]

    def test_a_read_operand_needs_a_character_after_it(self) -> None:
        """``v`` takes the next character as its operand only if there is
        one; at the end of the code it stands alone.
        """
        from esolangs.interpreters.tape_based.jaune import _parse

        assert [c.op for c in _parse("v+")] == ["v+"]
        assert [c.op for c in _parse("v")] == ["v"]
        assert [c.op for c in _parse("vv")] == ["v", "v"]

    def test_a_number_takes_the_operator_that_follows_it(self) -> None:
        """``3+`` is a single counted command; a number alone is dropped."""
        from esolangs.interpreters.tape_based.jaune import _parse

        assert [(c.op, c.arg) for c in _parse("3+")] == [("+", 3)]
        assert [(c.op, c.arg) for c in _parse("12+")] == [("+", 12)]
        assert _parse("12") == []

    def test_an_ignored_character_after_the_first_still_advances(self) -> None:
        """The parser steps past an unknown character, wherever it sits."""
        assert run_program("^x^.") == "00"


class TestErrors:
    def test_undefined_label(self) -> None:
        with pytest.raises(HaltError, match="undefined label"):
            run_program("1?^.")

    def test_undefined_subroutine(self) -> None:
        with pytest.raises(HaltError, match="undefined subroutine"):
            run_program("1@^.")

    def test_jump_on_zero_to_undefined_label(self) -> None:
        with pytest.raises(HaltError, match="undefined label"):
            run_program("1!")

    def test_the_return_error_reads_in_full(self) -> None:
        """The whole message, not just the fragment a ``match=`` looks for."""
        with pytest.raises(HaltError) as caught:
            run_program(";^")
        assert str(caught.value) == "; with no active subroutine call"


class TestMachine:
    def test_the_vm_view_tracks_the_run(self) -> None:
        """``ip``/``memory``/``stack`` are what the debugger reads, so they run."""
        from esolangs.interpreters.tape_based.jaune import _Machine

        machine = _Machine("6+5+^.", ScriptedIO())
        assert machine.ip == 0
        assert machine.memory == [0]
        while not machine.halted:
            machine.step()
        assert machine.ip == 4  # the cursor advanced with the run
        assert machine.memory == [11]  # 6 + 5, in the cell the program built

        # `stack` is the call stack, and only a call puts anything on it.
        called = _Machine("1@2@^.1$5+;2$3+;", ScriptedIO())
        depths = []
        while not called.halted:
            called.step()
            depths.append(len(called.stack))
        assert max(depths) == 1  # the two calls nest one deep, not zero
        assert called.stack == []  # and both returned


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.jaune import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "6+5+^."


@pytest.mark.parametrize(("code", "expected"), [("+12^.", "1"), ("-12^.", "-1")])
def test_a_sign_without_an_operand_command_remains_a_bare_operation(
    code: str, expected: str
) -> None:
    assert run_program(code) == expected


def test_a_non_ascii_digit_is_not_a_count() -> None:
    """Pins ASCII-only counts: Arabic-Indic three is ignored, so ``+`` adds 1."""
    assert run_program("\u0663+^.") == "1"
