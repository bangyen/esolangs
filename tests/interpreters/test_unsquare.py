"""Unit tests for the Unsquare interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.unsquare import run


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
        assert run_program("-Po") == "-2"  # -2 is not a valid code point
        assert run_program("xxPo") == "\x00"

    def test_swap(self) -> None:
        assert run_program("OISo") == "\x00"

    def test_read_input(self) -> None:
        assert run_program("iPo", "7\n") == "\x00"

    def test_read_pushes_first_char(self) -> None:
        assert run_program("iPo", "hi\n") == "\x00"  # acc is 0, P pushes it

    def test_read_blank_lines_reprompt(self) -> None:
        assert run_program("iPo", "\n\n7\n") == "\x00"

    def test_print_letter(self) -> None:
        assert run_program("+" * 32 + "Po") == "@"

    def test_loop_skips_when_acc_01(self) -> None:
        assert run_program("O>I<") == ""
        assert run_program("I>I<") == ""

    def test_loop_counts_down(self) -> None:
        # acc 4: each pass pushes acc, prints, and subtracts 2; the > records
        # and re-checks until acc reaches 0, then skips past the <.
        assert run_program("++>Po-<") == "\x04\x02"

    def test_error_empty_stack(self) -> None:
        with pytest.raises(HaltError):
            run_program("A")
        with pytest.raises(HaltError):
            run_program("o")
        with pytest.raises(HaltError):
            run_program("S")

    def test_error_unmatched_brackets(self) -> None:
        with pytest.raises(HaltError):
            run_program("<")
        with pytest.raises(HaltError):
            run_program(">")

    def test_empty_program(self) -> None:
        assert run_program("") == ""


class TestStepMachine:
    def test_snapshot_includes_the_input_cursor(self) -> None:
        from esolangs.interpreters.stack_based.unsquare import _Machine

        machine = _Machine("i", ScriptedIO("hi"))
        before = machine.snapshot()
        machine.step()  # i reads a line, pushing its first character
        assert machine.snapshot() != before
        assert machine.io.position() == 1
        assert machine.stack == [ord("h")]

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.stack_based.unsquare import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("Io", ScriptedIO())) is True

    def test_loop_is_detected_as_a_cycle(self) -> None:
        # IIAx pushes 1 twice, pops to acc=1, then doubles to acc=2 (outside
        # {0, 1}); the empty-body >< loop then repeats forever with every
        # field unchanged -- a genuine state cycle, not unbounded growth.
        from esolangs.interpreters.stack_based.unsquare import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("IIAx><", ScriptedIO())) is False

    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.stack_based.unsquare import _Machine

        machine = _Machine("", ScriptedIO())
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.stack == []
