r"""Unit tests for the Unsquare interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.unsquare import run
from tests.interpreters.contract import (
    CycleContract,
    InputCursorContract,
    StateViewContract,
)


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class TestUnsquare:
    def test_push_and_print(self) -> None:
        assert run_program("Io") == "\x01"
        assert run_program("Oo") == "\x00"

    def test_print_does_not_pop(self) -> None:
        assert run_program("Ooo") == "\x00\x00"

    def test_accumulator_ops(self) -> None:
        assert run_program("I+Po") == "\x02"
        assert run_program("++Po") == "\x04"
        assert run_program("-Po") == "-2"  # -2 is not a valid code point.
        assert run_program("xxPo") == "\x00"
        # The doubling above runs on.
        # zero.
        assert run_program("+xPo") == "\x04"
        assert run_program("+xxPo") == "\x08"

    def test_swap(self) -> None:
        assert run_program("OISo") == "\x00"

    def test_pop_puts_the_value_in_the_accumulator(self) -> None:
        r"""``A`` is only otherwise tested for the error it raises when empty."""
        assert run_program("IAPo") == "\x01"
        assert run_program("+PA+Po") == "\x04"

    def test_swap_exchanges_both_of_the_top_two(self) -> None:
        r"""Reading only the new top cannot see what went underneath it."""
        # the accumulator carries.
        # Then I pushes 1, and the swap.
        assert run_program("+P++PISoAo") == "\x06\x01"
        # and with only the two, the.
        assert run_program("+P++PSoAo") == "\x02\x06"

    def test_read_input(self) -> None:
        assert run_program("iPo", "7\n") == "\x00"

    def test_read_pushes_first_char(self) -> None:
        assert run_program("iPo", "hi\n") == "\x00"  # acc is 0, P pushes it.

    def test_read_blank_lines_reprompt(self) -> None:
        assert run_program("iPo", "\n\n7\n") == "\x00"

    def test_a_whitespace_only_line_counts_as_blank(self) -> None:
        r"""The re-prompt is on ``strip()``, not on emptiness."""
        assert run_program("io", "   \n7\n") == "7"

    def test_print_letter(self) -> None:
        assert run_program("+" * 32 + "Po") == "@"

    def test_printing_at_the_code_point_boundaries(self) -> None:
        r"""``o`` prints a character, or a decimal when the value is not one."""
        # the surrogate block is.
        # are not.
        assert run_program("io", chr(0xD800)) == "55296"
        assert run_program("io", chr(0xDFFF)) == "57343"
        assert run_program("io", chr(0xD7FF)) == "\ud7ff"
        assert run_program("io", chr(0xE000)) == "\ue000"
        # the top of the range is a.
        assert run_program("io", chr(0x10FFFF)) == "\U0010ffff"
        assert run_program("+xxxx+xxxxxxxxxxxxxxxPo") == "1114112"

    def test_a_negative_is_masked_before_it_is_judged(self) -> None:
        r"""``o`` tests the low 32 bits, but falls back to the whole value."""
        assert run_program("-" + "x" * 31 + "Po") == "\x00"

    def test_loop_skips_when_acc_01(self) -> None:
        r"""Both 0 and 1 skip the body -- and the 1 needs arranging."""
        assert run_program("O>I<") == ""
        assert run_program("I>I<") == ""
        assert run_program("OIA>A<Po") == "\x01"

    def test_skipped_loop_counts_nested_brackets(self) -> None:
        # the accumulator starts at 0,.
        # nested >< inside must be.
        # *matching* <, leaving the.
        assert run_program(">I><I<Io") == "\x01"

    def test_loop_counts_down(self) -> None:
        # acc 4: each pass pushes acc,.
        # and re-checks until acc.
        assert run_program("++>Po-<") == "\x04\x02"

    def test_error_empty_stack(self) -> None:
        r"""Each refusal says which one it is."""
        with pytest.raises(HaltError, match=r"^empty stack$"):
            run_program("A")
        with pytest.raises(HaltError, match=r"^empty stack$"):
            run_program("o")
        with pytest.raises(HaltError, match=r"^swap needs two elements$"):
            run_program("S")
        with pytest.raises(HaltError, match=r"^swap needs two elements$"):
            run_program("IS")

    def test_error_unmatched_brackets(self) -> None:
        with pytest.raises(HaltError, match=r"^unmatched <$"):
            run_program("<")
        with pytest.raises(HaltError, match=r"^unmatched >$"):
            run_program(">")

    def test_empty_program(self) -> None:
        assert run_program("") == ""


class TestStepMachine:
    def test_the_read_pushes_the_first_character(self) -> None:
        r"""``i`` reads a line and pushes the byte the language says it does."""
        from esolangs.interpreters.stack_based.unsquare import _Machine

        machine = _Machine("i", ScriptedIO("hi"))
        machine.step()
        assert machine.stack == (ord("h"),)

    def test_memory_views_the_accumulator_not_the_stack(self) -> None:
        r"""``memory`` is the accumulator; ``stack`` is the stack."""
        from esolangs.interpreters.stack_based.unsquare import _Machine

        machine = _Machine("+I", ScriptedIO())
        for _ in range(2):
            machine.step()
        assert machine.memory == [2]  # the accumulator.
        assert machine.stack == (1,)  # what I pushed.

    def test_an_unmatched_bracket_leaves_the_machine_halted(self) -> None:
        r"""The cursor is moved to the end before the error is raised."""
        from esolangs.interpreters.stack_based.unsquare import _Machine

        machine = _Machine(">", ScriptedIO())
        with pytest.raises(HaltError, match=r"^unmatched >$"):
            machine.step()
        assert machine.halted
        assert machine.ind == 1

    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.stack_based.unsquare import _Machine

        machine = _Machine("", ScriptedIO())
        assert machine.halted
        machine.step()  # stepping a halted machine is.
        assert machine.stack == ()


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.unsquare import _Machine

    return _Machine(code, ScriptedIO())


def _reader(code: object, stdin: str) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.unsquare import _Machine

    return _Machine(code, ScriptedIO(stdin))


class TestContract(CycleContract, InputCursorContract, StateViewContract):
    r"""The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    reader = staticmethod(_reader)
    reading_program = "i"
    reading_stdin = "hi"
    halting_program = "Io"
    looping_program = "IIAx><"
    # `I` pushes and `o` prints, so.
    # while the jump stack stays.
    # separate slots, not one field.
    state_views = ("ind", "acc", "stack", "jumps", "ip", "memory")
    # The loop test's own program:.
    # stack, and the data stack,.
    viewing_program = "++>Po-<"


class TestStateViewValues:
    r"""The named views read the slots they claim, not one another."""

    def test_acc_and_jumps_are_their_own_slots(self) -> None:
        r"""Six steps into the loop all four hold different things."""
        machine = _machine("++>Po-<")
        for _ in range(6):
            machine.step()
        assert machine.acc == 2  # decremented once inside the.
        assert machine.jumps == (1,)  # the > that was entered.
        assert machine.stack == (4,)  # what P pushed on the first.
