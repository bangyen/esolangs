"""Unit tests for the Jaune interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.jaune import run
from tests.interpreters.contract import SnapshotContract


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class TestArithmetic:
    def test_add_and_output(self) -> None:
        assert run_program("6+5+^.") == "11"

    def test_subtract(self) -> None:
        assert run_program("8+3-^.") == "5"

    def test_bare_plus_is_one(self) -> None:
        assert run_program("+^.") == "1"

    def test_counted_command(self) -> None:
        assert run_program("++^.") == "2"

    def test_an_explicit_zero_count_still_adjusts_by_one(self) -> None:
        """``0+`` parses to a count of 0, which falls back to 1.

        Every other program spells its counts as a run or a positive
        number, so the ``or 1`` fallback was only ever reached through the
        bare ``+`` -- where the count is already 1 and the fallback is
        invisible.  A literal ``0`` is the one spelling that exercises it.
        """
        assert run_program("0+^.") == "1"
        assert run_program("0-^.") == "-1"


class TestInput:
    def test_read_digit(self) -> None:
        assert run_program("v^.", "7\n") == "7"

    def test_add_input(self) -> None:
        # the spec's adder: v+ reads a digit and adds it
        assert run_program("v+v+^.", "4\n5\n") == "9"

    def test_subtract_input(self) -> None:
        # 'v-' reads a digit and subtracts it, the mirror of 'v+'
        assert run_program("9+v-^.", "4\n") == "5"

    def test_input_eof(self) -> None:
        with pytest.raises(EOFError):
            run_program("v.", "")

    def test_an_empty_line_reads_as_zero(self) -> None:
        """A line the user ended immediately holds no digit, so it is 0.

        Running out of input raises, so the suite only ever reached the
        two ends of the read -- a digit, or EOF -- and never the line that
        is present but empty, which is where the fallback lives.
        """
        assert run_program("v^.", "\n") == "0"
        assert run_program("5+v+^.", "\n") == "5"


class TestMemory:
    def test_hold_cell(self) -> None:
        # the spec's second adder: read a, read b, hold b, add to a
        assert run_program("v+>v+#<&^.", "3\n4\n") == "7"

    def test_move_and_extend(self) -> None:
        assert run_program(">+>+<^>^.") == "11"

    def test_zero_cell(self) -> None:
        assert run_program("5+%^.") == "0"

    def test_pointer_left_of_zero_inserts_a_cell(self) -> None:
        # '<' at cell 0 inserts a fresh zero cell to the left
        assert run_program("<^.") == "0"

    def test_the_inserted_cell_is_left_of_the_old_one(self) -> None:
        """``<`` at cell 0 puts the new cell *before* the old contents.

        On a blank tape every cell is 0, so which side the insert lands on
        makes no difference to what prints.  Writing a value first tells
        the two apart: the pointer must end on the fresh zero, with the
        old value one step to its right.
        """
        assert run_program("5+<^.") == "0"
        assert run_program("5+<>^.") == "5"

    def test_the_hold_cell_starts_at_zero(self) -> None:
        """``&`` before any ``#`` adds nothing.

        Every other program copies into the hold cell before adding from
        it, so its initial value was never read.
        """
        assert run_program("&^.") == "0"


class TestControlFlow:
    def test_loop_adder(self) -> None:
        # v+>v+1:1-<1+>1?<^. : read a, b; while b: b--, a++; print a
        assert run_program("v+>v+1:1-<1+>1?<^", "3\n4\n") == "7"

    def test_multiplier(self) -> None:
        # the spec's multiplier: a * b
        assert run_program("v+1->v+#<1:2!>&<1-1?2:>^", "3\n4\n") == "12"

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
        """``;`` consumes one character, leaving the next definition whole.

        Every ``;`` the suite runs is the last character of its program,
        so a ``;`` that swallowed what follows it would look identical.
        Two subroutines in a row put a definition in that position.
        """
        # call 1 then 2; subroutine 1 adds 5, subroutine 2 adds 3
        assert run_program("1@2@^.1$5+;2$3+;") == "8"


class TestParsing:
    def test_bare_number_is_ignored(self) -> None:
        # a number with no following operator is a no-op
        assert run_program("123^.") == "0"

    def test_unknown_characters_are_ignored(self) -> None:
        assert run_program("x^.") == "0"

    def test_an_uppercase_letter_is_no_more_a_command_than_a_lowercase_one(
        self,
    ) -> None:
        """``X`` is ignored, as every unrecognized character is.

        The alphabets the parser tests against are written as strings, and
        a string only ever contained the operators themselves -- so a
        character that is *nearly* one of them, differing only in case,
        never came through to show that the sets are exact.
        """
        assert run_program("X^.") == "0"
        assert run_program("1X^.") == "0"

    def test_an_ignored_character_after_the_first_still_advances(self) -> None:
        """The parser steps past an unknown character, wherever it sits.

        Every program that skips one puts it at the very start, where
        advancing to index 1 and *assigning* index 1 agree; a second
        command in front of it is what separates them.
        """
        assert run_program("^x^.") == "00"

    def test_bare_operator_requires_a_number(self) -> None:
        with pytest.raises(ValueError, match="requires a number"):
            run_program("?")

    def test_runs_of_an_operator_carry_their_length(self) -> None:
        """``++`` is one command repeated twice, not two commands.

        Parsing is only ever checked through what a program prints, where
        a run and a sequence of singles reach the same total -- so the
        count the parser attaches went unread.
        """
        from esolangs.interpreters.tape_based.jaune import _parse

        assert [(c.op, c.arg) for c in _parse("+++")] == [("+", 3)]
        assert [(c.op, c.arg) for c in _parse("--")] == [("-", 2)]
        assert [(c.op, c.arg) for c in _parse("++-")] == [("+", 2), ("-", 1)]

    def test_a_read_operand_needs_a_character_after_it(self) -> None:
        """``v`` takes the next character as its operand only if there is
        one; at the end of the code it stands alone.

        The lookahead is a boundary the suite never reached, since every
        ``v`` it uses has something after it.
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

    def test_return_without_a_call(self) -> None:
        with pytest.raises(HaltError, match="no active subroutine"):
            run_program(";^")

    def test_the_return_error_reads_in_full(self) -> None:
        """The whole message, not the fragment the other tests match on.

        ``match=`` is a substring search, so every assertion above passes
        on a message padded or reworded around the phrase it looks for.
        """
        with pytest.raises(HaltError) as caught:
            run_program(";^")
        assert str(caught.value) == "; with no active subroutine call"


class TestMachine:
    def test_step_after_halt_is_a_no_op(self) -> None:
        from esolangs.interpreters.tape_based.jaune import _Machine

        machine = _Machine("^", ScriptedIO())
        assert not machine.halted
        machine.step()
        assert machine.halted
        machine.step()  # must not raise

    def test_the_vm_view_tracks_the_run(self) -> None:
        """``ip``/``memory``/``stack`` are what the debugger reads, so they run.

        These are the shared VM-shaped names rather than jaune's own, and
        nothing else here touches them: the protocol sweep drives ``step``
        and ``halted``, and the snapshot contract reads ``snapshot``.  A
        property wired to the wrong field -- ``memory`` handing back the
        call stack, say -- would still pass every other test in this file.

        Asserted as movement rather than as pinned constants: the point is
        that each name follows the field it claims, and the subroutine
        program is the one that makes ``stack`` non-empty at all.
        """
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
