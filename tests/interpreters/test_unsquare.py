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
        # The doubling above runs on zero, which any multiplier leaves at
        # zero.  Doubling something first says the factor is 2.
        assert run_program("+xPo") == "\x04"
        assert run_program("+xxPo") == "\x08"

    def test_swap(self) -> None:
        assert run_program("OISo") == "\x00"

    def test_pop_puts_the_value_in_the_accumulator(self) -> None:
        """``A`` is only otherwise tested for the error it raises when empty.

        What it does on a stack that *has* something was never asserted, so
        the pop could have discarded the value entirely and only a later
        use of the accumulator would notice.
        """
        assert run_program("IAPo") == "\x01"
        assert run_program("+PA+Po") == "\x04"

    def test_swap_exchanges_both_of_the_top_two(self) -> None:
        """Reading only the new top cannot see what went underneath it.

        ``o`` does not pop, so every swap test read one element and left
        the other unchecked -- and a swap that overwrites *both* slots with
        the same value looks identical from the top alone.  Printing the
        top, popping it with ``A``, and printing what surfaces says both
        moved.  A third element underneath is there because the indices
        involved only diverge on a stack deeper than two.
        """
        # the accumulator carries across pushes: +P pushes 2, ++P pushes 6.
        # Then I pushes 1, and the swap exchanges the 1 and the 6.
        assert run_program("+P++PISoAo") == "\x06\x01"
        # and with only the two, the pair still comes back in order
        assert run_program("+P++PSoAo") == "\x02\x06"

    def test_read_input(self) -> None:
        assert run_program("iPo", "7\n") == "\x00"

    def test_read_pushes_first_char(self) -> None:
        assert run_program("iPo", "hi\n") == "\x00"  # acc is 0, P pushes it

    def test_read_blank_lines_reprompt(self) -> None:
        assert run_program("iPo", "\n\n7\n") == "\x00"

    def test_print_letter(self) -> None:
        assert run_program("+" * 32 + "Po") == "@"

    def test_printing_at_the_code_point_boundaries(self) -> None:
        """``o`` prints a character, or a decimal when the value is not one.

        Which values are "not one" was only tested at -2, far outside every
        boundary, so both edges of the surrogate block and the top of the
        range could move without any program noticing.  Each is checked
        from both sides.

        The accumulator is built from ``+``/``-``/``x``, so it is always
        even and cannot reach the odd boundaries; those are read through
        ``i`` instead, which pushes a character's code point.
        """
        # the surrogate block is rejected at both ends, and its neighbours
        # are not
        assert run_program("io", chr(0xD800)) == "55296"
        assert run_program("io", chr(0xDFFF)) == "57343"
        assert run_program("io", chr(0xD7FF)) == "\ud7ff"
        assert run_program("io", chr(0xE000)) == "\ue000"
        # the top of the range is a character; one past it is not
        assert run_program("io", chr(0x10FFFF)) == "\U0010ffff"
        assert run_program("+xxxx+xxxxxxxxxxxxxxxPo") == "1114112"

    def test_loop_skips_when_acc_01(self) -> None:
        assert run_program("O>I<") == ""
        assert run_program("I>I<") == ""

    def test_skipped_loop_counts_nested_brackets(self) -> None:
        # the accumulator starts at 0, so the leading > skips its body; the
        # nested >< inside must be counted so the skip stops at the
        # *matching* <, leaving the trailing Io to push and print
        assert run_program(">I><I<Io") == "\x01"

    def test_loop_counts_down(self) -> None:
        # acc 4: each pass pushes acc, prints, and subtracts 2; the > records
        # and re-checks until acc reaches 0, then skips past the <.
        assert run_program("++>Po-<") == "\x04\x02"

    def test_error_empty_stack(self) -> None:
        """Each refusal says which one it is.

        The four messages went unasserted, so any of them could have become
        empty -- or all four the same -- and the raise alone would still
        pass.  ``S`` is the one that distinguishes itself: it needs *two*
        elements, so it refuses a stack that is merely short rather than
        empty.
        """
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
