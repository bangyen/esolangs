"""Unit tests for the Jaune interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.jaune import run


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


class TestInput:
    def test_read_digit(self) -> None:
        assert run_program("v^.", "7\n") == "7"

    def test_add_input(self) -> None:
        # the spec's adder: v+ reads a digit and adds it
        assert run_program("v+v+^.", "4\n5\n") == "9"

    def test_input_eof(self) -> None:
        with pytest.raises(EOFError):
            run_program("v.", "")


class TestMultiply:
    """The multiply program from :func:`esolangs.tools.boolean.jaune_multiply`.

    It reads two sentinel-delimited decimal operands -- the digits of the
    first, a ``*`` line, the digits of the second, a ``#`` line -- and prints
    their product.  The construction handles any operand length, so the
    generator takes no digit-count parameter (see docs/walls.md).
    """

    def test_multiplies_two_operands(self) -> None:
        from esolangs.tools.boolean import jaune_multiply

        stdin = "".join(line + "\n" for line in ["1", "2", "*", "3", "4", "#"])
        assert run_program(jaune_multiply(), stdin) == "408"

    def test_multiplies_operands_of_different_lengths(self) -> None:
        from esolangs.tools.boolean import jaune_multiply

        stdin = "".join(line + "\n" for line in ["7", "*", "1", "0", "9", "#"])
        assert run_program(jaune_multiply(), stdin) == "763"


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


class TestParsing:
    def test_bare_number_is_ignored(self) -> None:
        # a number with no following operator is a no-op
        assert run_program("123^.") == "0"

    def test_unknown_characters_are_ignored(self) -> None:
        assert run_program("x^.") == "0"

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


class TestMachine:
    def test_step_after_halt_is_a_no_op(self) -> None:
        from esolangs.interpreters.tape_based.jaune import _Machine

        machine = _Machine("^", ScriptedIO())
        assert not machine.halted
        machine.step()
        assert machine.halted
        machine.step()  # must not raise
