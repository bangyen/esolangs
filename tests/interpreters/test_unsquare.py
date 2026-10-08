"""Unit tests for the Unsquare interpreter."""

from functools import partial

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.unsquare import run
from tests.interpreters import runner
from tests.interpreters.contract import (
    CycleContract,
    InputCursorContract,
    StateViewContract,
)
from tests.interpreters.cursorless_io import PositionlessIO
from tests.raises import raises_message

run_program = partial(runner.run_program, run, suppress_eof=False)


class TestUnsquare:
    def test_push_and_print(self) -> None:
        assert run_program("Io") == "\x01"
        assert run_program("Oo") == "\x00"

    def test_accumulator_ops(self) -> None:
        assert run_program("I+Po") == "\x02"
        assert run_program("++Po") == "\x04"
        assert run_program("-Po") == "-2"  # -2 is not a valid code point
        assert run_program("xxPo") == "\x00"
        # The doubling above runs on zero, which any multiplier leaves at
        # zero.  Doubling something first says the factor is 2.
        assert run_program("+xPo") == "\x04"
        assert run_program("+xxPo") == "\x08"

    def test_pop_puts_the_value_in_the_accumulator(self) -> None:
        """``A`` is only otherwise tested for the error it raises when empty."""
        assert run_program("IAPo") == "\x01"
        assert run_program("+PA+Po") == "\x04"

    def test_swap_exchanges_both_of_the_top_two(self) -> None:
        """Reading only the new top cannot see what went underneath it."""
        # the accumulator carries across pushes: +P pushes 2, ++P pushes 6.
        # Then I pushes 1, and the swap exchanges the 1 and the 6.
        assert run_program("+P++PISoAo") == "\x06\x01"
        # and with only the two, the pair still comes back in order
        assert run_program("+P++PSoAo") == "\x02\x06"

    def test_read_blank_lines_reprompt(self) -> None:
        assert run_program("iPo", "\n\n7\n") == "\x00"

    def test_input_preserves_spaces(self) -> None:
        """A space is a character, not a request to skip a line."""
        assert run_program("io", "   \n7\n") == " "

    def test_printing_at_the_code_point_boundaries(self) -> None:
        """``o`` prints a character, or a decimal when the value is not one."""
        # the surrogate block is rejected at both ends, and its neighbours
        # are not
        assert run_program("io", chr(0xD800)) == "55296"
        assert run_program("io", chr(0xDFFF)) == "57343"
        assert run_program("io", chr(0xD7FF)) == "\ud7ff"
        assert run_program("io", chr(0xE000)) == "\ue000"
        # the top of the range is a character; one past it is not
        assert run_program("io", chr(0x10FFFF)) == "\U0010ffff"
        assert run_program("+xxxx+xxxxxxxxxxxxxxxPo") == "1114112"

    def test_a_negative_is_masked_before_it_is_judged(self) -> None:
        """``o`` tests the low 32 bits, but falls back to the whole value."""
        assert run_program("-" + "x" * 31 + "Po") == "\x00"

    def test_loop_skips_when_acc_01(self) -> None:
        """Both 0 and 1 skip the body -- and the 1 needs arranging."""
        assert run_program("O>I<") == ""
        assert run_program("I>I<") == ""
        assert run_program("OIA>A<Po") == "\x01"

    def test_skipped_loop_counts_nested_brackets(self) -> None:
        # the accumulator starts at 0, so the leading > skips its body; the
        # nested >< inside must be counted so the skip stops at the
        # *matching* <, leaving the trailing Io to push and print
        assert run_program(">I><I<Io") == "\x01"

    def test_error_empty_stack(self) -> None:
        """Each refusal says which one it is."""
        with raises_message(HaltError, "empty stack"):
            run_program("A")
        with raises_message(HaltError, "empty stack"):
            run_program("o")
        with raises_message(HaltError, "swap needs two elements"):
            run_program("S")
        with raises_message(HaltError, "swap needs two elements"):
            run_program("IS")

    def test_error_unmatched_brackets(self) -> None:
        with raises_message(HaltError, "unmatched <"):
            run_program("<")
        with raises_message(HaltError, "unmatched >"):
            run_program(">")
        # Entering the loop (acc 2) must refuse it too; only a skip used to
        # look for the partner, so this ran to the end silently (06c55183).
        with raises_message(HaltError, "unmatched >"):
            run_program("+>")


class TestStepMachine:
    def test_the_read_pushes_the_first_character(self) -> None:
        """A character read pushes the next character code."""
        from esolangs.interpreters.stack_based.unsquare import _Machine

        machine = _Machine("i", ScriptedIO("hi"))
        machine.step()
        assert machine.stack == (ord("h"),)

    def test_memory_views_the_accumulator_not_the_stack(self) -> None:
        """``memory`` is the accumulator; ``stack`` is the stack."""
        from esolangs.interpreters.stack_based.unsquare import _Machine

        machine = _Machine("+I", ScriptedIO())
        for _ in range(2):
            machine.step()
        assert machine.memory == [2]  # the accumulator
        assert machine.stack == (1,)  # what I pushed

    def test_an_unmatched_bracket_leaves_the_machine_halted(self) -> None:
        """The cursor is moved to the end before the error is raised."""
        from esolangs.interpreters.stack_based.unsquare import _Machine

        machine = _Machine(">", ScriptedIO())
        with raises_message(HaltError, "unmatched >"):
            machine.step()
        assert machine.halted
        assert machine.ind == 1

    def test_a_close_with_acc_zero_falls_through(self) -> None:
        """Wiki: ``<`` jumps back only "if the accumulator is not 0 nor 1"."""
        from esolangs.interpreters.stack_based.unsquare import _Machine

        machine = _Machine("+>-<", ScriptedIO())
        steps = 0
        while not machine.halted:
            machine.step()
            steps += 1
        assert steps == 4

    def test_a_read_loop_on_a_cursorless_port_is_not_a_cycle(self) -> None:
        """A port with no cursor reports position 0; the snapshot counts reads."""
        from esolangs.interpreters.stack_based.unsquare import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine("+>iA+<", PositionlessIO("\x00" * 10))
        with pytest.raises(EOFError):
            run_until_halt_or_cycle(machine, limit=100)


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.unsquare import _Machine

    return _Machine(code, ScriptedIO())


def _reader(code: object, stdin: str) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.unsquare import _Machine

    return _Machine(code, ScriptedIO(stdin))


class TestContract(CycleContract, InputCursorContract, StateViewContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    reader = staticmethod(_reader)
    reading_program = "i"
    reading_stdin = "hi"
    halting_program = "Io"
    looping_program = "IIAx><"
    # `I` pushes and `o` prints, so the cursor and the data stack both move
    # while the jump stack stays empty -- which is the point: they are
    # separate slots, not one field read under four names.
    state_views = ("ind", "acc", "stack", "jumps", "ip", "memory")
    # The loop test's own program: it moves the accumulator, the jump
    # stack, and the data stack, where "Io" moved only the last.
    viewing_program = "++>Po-<"


class TestStateViewValues:
    """The named views read the slots they claim, not one another."""

    def test_acc_and_jumps_are_their_own_slots(self) -> None:
        """Six steps into the loop all four hold different things."""
        machine = _machine("++>Po-<")
        for _ in range(6):
            machine.step()
        assert machine.acc == 2  # decremented once inside the body
        assert machine.jumps == (1,)  # the > that was entered
        assert machine.stack == (4,)  # what P pushed on the first pass


def test_loading_a_stack_detaches_it_and_preserves_other_state() -> None:
    from esolangs.interpreters.stack_based.unsquare import _Machine

    machine = _Machine("+o", ScriptedIO())
    machine.step()
    values = [65, 66]
    machine.load(values)
    values[1] = 67
    assert machine.stack == (65, 66)
    assert machine.acc == 2
    machine.step()
    assert machine.io.getvalue() == "B"
