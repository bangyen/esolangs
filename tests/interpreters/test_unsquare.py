"""Unit tests for the Unsquare interpreter."""

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

    def test_a_whitespace_only_line_counts_as_blank(self) -> None:
        """The re-prompt is on ``strip()``, not on emptiness.

        ``test_read_blank_lines_reprompt`` prints the *accumulator*, which
        is 0 whatever ``i`` pushed, so it cannot see what was read -- and
        its lines are genuinely empty, which both readings skip.  Printing
        what ``i`` pushed, from a line of spaces, is what separates them: a
        reader stopping at ``not line`` takes the space itself.
        """
        assert run_program("io", "   \n7\n") == "7"

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

    def test_a_negative_is_masked_before_it_is_judged(self) -> None:
        """``o`` tests the low 32 bits, but falls back to the whole value.

        The only negative anywhere else is -2, whose low 32 bits are
        4294967294 -- far outside the code-point range, so it prints as a
        decimal and the mask never shows.  ``-`` then 31 ``x`` makes
        -4294967296, whose low 32 bits are 0, and that prints as a
        character.  An interpreter treating every negative as unprintable
        passed the whole file.
        """
        assert run_program("-" + "x" * 31 + "Po") == "\x00"

    def test_loop_skips_when_acc_01(self) -> None:
        """Both 0 and 1 skip the body -- and the 1 needs arranging.

        Neither ``O`` nor ``I`` touches the accumulator, so the two cases
        below are both the *zero* one and the 1 in this test's name went
        untested: an interpreter skipping only on zero passed the whole
        file.  Getting a 1 into the accumulator takes pushing one and
        popping it back with ``A``.

        In ``OIA>A<Po`` the accumulator is 1 at the ``>``, so the body is
        skipped, the 0 that ``O`` pushed stays put, and ``P`` pushes the
        still-1 accumulator for ``o`` to print.  Entering instead would run
        the ``A``, which pops that 0 into the accumulator and prints 0.
        """
        assert run_program("O>I<") == ""
        assert run_program("I>I<") == ""
        assert run_program("OIA>A<Po") == "\x01"

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
    def test_the_read_pushes_the_first_character(self) -> None:
        """``i`` reads a line and pushes the byte the language says it does.

        The cursor and snapshot moving is the shared contract below; what
        lands on the stack is Unsquare's own.
        """
        from esolangs.interpreters.stack_based.unsquare import _Machine

        machine = _Machine("i", ScriptedIO("hi"))
        machine.step()
        assert machine.stack == (ord("h"),)

    def test_memory_views_the_accumulator_not_the_stack(self) -> None:
        """``memory`` is the accumulator; ``stack`` is the stack.

        ``state_views`` lists both, but the shared contract only checks
        that each name resolves and that *some* view moves over the run,
        which ``ind`` alone satisfies -- so ``memory`` returning the data
        stack, the exact aliasing that contract is named for, passed.
        ``+I`` leaves the two holding different things, which is what makes
        the difference visible.
        """
        from esolangs.interpreters.stack_based.unsquare import _Machine

        machine = _Machine("+I", ScriptedIO())
        for _ in range(2):
            machine.step()
        assert machine.memory == [2]  # the accumulator
        assert machine.stack == (1,)  # what I pushed

    def test_an_unmatched_bracket_leaves_the_machine_halted(self) -> None:
        """The cursor is moved to the end before the error is raised.

        ``test_error_unmatched_brackets`` checks the message, and the
        machine it came from is thrown away by ``run_program``.  But the
        placement is deliberate: the scan that fails has walked to the end
        of the code, and a caller that catches the HaltError should find a
        halted machine rather than one still sitting on the bracket.
        """
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
        machine.step()  # stepping a halted machine is a no-op
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
