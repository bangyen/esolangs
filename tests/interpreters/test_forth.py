"""Unit tests for the Forþ interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.forth import run
from tests.interpreters.contract import EmptyProgramContract


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class TestForth:
    def test_digits_and_letters(self) -> None:
        assert run_program("65.") == "\x05"
        assert run_program("A.") == "\n"

    def test_duplicate(self) -> None:
        assert run_program("5:..") == "\x05\x05"

    def test_arithmetic(self) -> None:
        assert run_program("23+.") == "\x05"
        assert run_program("95-.") == "\x04"
        assert run_program("28*.") == "\x10"
        assert run_program("84/.") == "\x02"
        assert run_program("85%.") == "\x03"

    def test_complement(self) -> None:
        assert run_program("0~.") == "\xff"

    def test_division_truncates_toward_zero(self) -> None:
        # 0 9 / is 0, then ~0 is -1, printed as byte 0xff
        assert run_program("09/~.") == "\xff"

    def test_swap(self) -> None:
        assert run_program("65v..") == "\x06\x05"

    def test_reverse(self) -> None:
        assert run_program("123o...") == "\x01\x02\x03"

    def test_rotate(self) -> None:
        assert run_program("123c...") == "\x01\x03\x02"

    def test_branch(self) -> None:
        assert run_program("1(F4*5+.)") == "A"
        assert run_program("0(F4*5+.)") == ""

    def test_loop(self) -> None:
        # push the seed 0 and the bytes for 'H' (72) and 'i' (105); the
        # [.] loop prints both and stops at the 0 seed
        assert run_program("0F7*0+F4*C+[.]") == "Hi"

    def test_nested_brackets(self) -> None:
        # a nested loop is matched to its own closing bracket, not the outer one
        assert run_program("0[[.]]") == ""

    def test_store_and_call(self) -> None:
        assert run_program("1{65.}1;") == "\x05"
        assert run_program("1{F4*5+.}1;") == "A"

    def test_read_line_pushes_rightmost_on_top(self) -> None:
        assert run_program(",..", "hi") == "ih"

    def test_read_and_normalize(self) -> None:
        # , reads '0' (48), 6 8 * is 48, - leaves 0
        assert run_program(",68*-.", "0") == "\x00"

    def test_unknown_char_is_ignored(self) -> None:
        # an unknown char does nothing, even with a near-empty stack
        assert run_program("a5.") == "\x05"
        # with two elements it leaves the stack untouched (no-op)
        assert run_program("65a.") == "\x05"

    def test_empty_stack_pop_halts(self) -> None:
        with pytest.raises(HaltError):
            run_program(".")

    def test_binary_underflow_halts(self) -> None:
        with pytest.raises(HaltError):
            run_program("9/")

    def test_rotate_underflow_halts(self) -> None:
        with pytest.raises(HaltError):
            run_program("12c")

    def test_division_by_zero_halts(self) -> None:
        with pytest.raises(HaltError):
            run_program("50/")
        with pytest.raises(HaltError):
            run_program("50%")

    def test_unterminated_bracket_halts(self) -> None:
        with pytest.raises(HaltError):
            run_program("(5")
        with pytest.raises(HaltError):
            run_program("[")

    def test_nested_error_is_discarded(self) -> None:
        """A called scope's underflow returns 3, which the caller ignores."""
        assert run_program("1{/}1;") == ""

    def test_nested_empty_pop_is_fatal(self) -> None:
        """An empty-stack pop inside a called scope halts the whole program."""
        with pytest.raises(HaltError):
            run_program("1{.};")


class TestStepMachine:
    def test_arithmetic_wraps_to_a_signed_32_bit_range(self) -> None:
        """Results wrap into -2**31 .. 2**31-1, which only the stack shows.

        ``.`` prints ``value & 0xFF``, so every test that reads output sees
        the low byte alone -- the wrap could land anywhere above it and the
        printed character would not change.  Squaring 9 five times passes
        2**31 and has to come back negative.
        """
        from esolangs.interpreters.stack_based.forth import _Machine

        machine = _Machine("9:*:*:*:*", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.stack == [-501334399]

    def test_a_loop_reenters_its_frame_each_pass(self) -> None:
        """A loop restarts its body until the top reaches zero.

        The frame it re-enters has to be marked a loop, or the second pass
        would not run.  Counting down while duplicating leaves one value
        per pass, so the stack shows how many times the body ran.
        """
        from esolangs.interpreters.stack_based.forth import _Machine

        machine = _Machine("3[:1-]", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.stack == [3, 2, 1, 0]

    def test_step_tracks_stack_and_active_frame_cursor(self) -> None:
        from esolangs.interpreters.stack_based.forth import _Machine

        machine = _Machine("65.", ScriptedIO())
        assert (machine.stack, machine.frames[0].pc) == ([], 0)
        machine.step()  # 6 pushes
        assert (machine.stack, machine.frames[0].pc) == ([6], 1)
        machine.step()  # 5 pushes
        assert machine.stack == [6, 5]
        machine.step()  # . pops and prints the low byte
        assert machine.io.getvalue() == "\x05"
        machine.step()  # finalizing the finished frame halts the machine
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.frames == []

    def test_nested_scope_pushes_a_frame_and_aborts_discard_the_error(self) -> None:
        from esolangs.interpreters.stack_based.forth import _Machine

        machine = _Machine("1{/}1;", ScriptedIO())
        for _ in range(4):  # 1 {/} 1 ; -> the ; pushes the "/" scope
            machine.step()
        assert len(machine.frames) == 2
        machine.step()  # the "/" underflow aborts the scope (and ends the run)
        assert machine.halted
        assert machine.error is False  # the nested error is discarded

    def test_snapshot_includes_the_input_cursor(self) -> None:
        from esolangs.interpreters.stack_based.forth import _Machine

        machine = _Machine(",", ScriptedIO("hi"))
        before = machine.snapshot()
        machine.step()  # , reads the line, pushing each byte
        assert machine.snapshot() != before
        assert machine.io.position() == 1
        assert machine.stack == [104, 105]

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.stack_based.forth import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("65.", ScriptedIO())) is True

    def test_loop_is_detected_as_a_cycle(self) -> None:
        """1[] : the empty loop body never clears the top, so it spins."""
        from esolangs.interpreters.stack_based.forth import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("1[]", ScriptedIO())) is False


class TestContract(EmptyProgramContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
