"""Unit tests for the Forþ interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.forth import run
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
)


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

    def test_uppercase_past_f_is_not_a_digit(self) -> None:
        """Only A-F push; G is past the end of the hex run and is ignored."""
        assert run_program("0G.") == "\x00"

    def test_x_is_neither_an_operator_nor_a_bracket(self) -> None:
        """X sits outside every command class, so it leaves the stack alone.

        A stray X read as an opener would scan to the end of the program
        and abort; read as a binary operator it would underflow.  Either
        way the run would halt instead of printing.
        """
        assert run_program("X5.") == "\x05"

    def test_calling_an_unstored_scope_runs_nothing(self) -> None:
        """``;`` on a key with no scope pushes an empty frame, not nothing."""
        assert run_program("1;") == ""

    def test_a_branch_scope_stops_at_its_closing_bracket(self) -> None:
        """The scope excludes the ``)``, so what follows runs once, not twice."""
        assert run_program("1(5:).") == "\x05"

    def test_a_live_nested_branch_matches_the_outer_bracket(self) -> None:
        """Depth is counted up as well as down, so the outer scope is whole.

        Truncating the outer scope at the inner ``)`` would leave it with an
        unterminated ``(``, aborting the nested scope and printing nothing.
        """
        assert run_program("1((5.))") == "\x05"

    def test_a_loop_inside_a_called_scope_finishes(self) -> None:
        """A loop two frames deep re-enters the top frame, not frame 1."""
        assert run_program("1{3[:1-]A.}1;") == "\n"

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

    def test_the_wrap_folds_at_exactly_two_to_the_thirty_first(self) -> None:
        """2**31 is the first value that wraps, and it lands on the floor.

        The modulus has to be 2**32: a wider one would leave 2**31 alone,
        and no smaller product reaches the boundary to show it.  2**16
        times 2**15 is the product built here.
        """
        from esolangs.interpreters.stack_based.forth import _Machine

        machine = _Machine("2:*:*:*:*88*8*8*8**", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.stack == [-2147483648]

    def test_an_unstored_key_calls_an_empty_scope(self) -> None:
        """``;`` falls back to the empty string, so the pushed frame has code.

        A missing fallback would push ``None`` and the next step would fail
        measuring its length; a non-empty one would run commands nobody
        stored.
        """
        from esolangs.interpreters.stack_based.forth import _Machine

        machine = _Machine("1;", ScriptedIO())
        machine.step()  # 1 pushes the key
        machine.step()  # ; pops it and pushes the stored scope
        assert [frame.code for frame in machine.frames] == ["1;", ""]

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


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.forth import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, CycleContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
    machine = staticmethod(_machine)
    halting_program = "65."
    looping_program = "1[]"
