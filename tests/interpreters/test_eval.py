r"""Unit tests for the Eval interpreter."""

import io
from contextlib import redirect_stdout

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.stack_based.eval import _Machine, run


def run_and_capture(code: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestEval:
    def test_hello_world(self) -> None:
        assert run_and_capture('"Hello, World!".') == "Hello, World!"

    def test_push_zero_increment(self) -> None:
        assert run_and_capture("0+.") == "1"

    def test_stringmode_backtick(self) -> None:
        r"""A backtick inside stringmode becomes a double quote."""
        assert run_and_capture('"`".') == '"'

    def test_charmode(self) -> None:
        r"""' wraps the string in double quotes."""
        assert run_and_capture("'ab\".") == '"ab"'

    def test_a_literal_ends_at_the_first_quote_not_the_last(self) -> None:
        r"""Two literals in one program stay separate."""
        assert run_and_capture('"a"."b".') == "ab"

    def test_a_literal_advances_the_cursor_from_where_it_started(self) -> None:
        r"""A literal moves the cursor *on* by its length, not *to* it."""
        state = _Machine('0+."a".', ScriptedIO())
        for _ in range(3):
            state.step()
        assert state.ind == 3

        state.step()  # the literal at index 3: past.
        assert state.ind == 6
        assert state.stk[state.ptr] == ("a",)

    def test_only_the_two_quotes_start_a_literal(self) -> None:
        r"""No other character opens stringmode -- the rest are commands or."""
        commands = set("`^0+-.=;~*?!\"'")
        for char in map(chr, range(0x20, 0x7F)):
            if char in commands:
                continue
            state = _Machine(char, ScriptedIO())
            state.step()
            assert state.stk == ((), ()), f"{char!r} was not a no-op"
            assert state.ind == 1

    def test_output_goes_to_the_supplied_io(self) -> None:
        r"""``run`` writes through its ``io`` argument, not a fresh default one."""
        scripted = ScriptedIO("")
        run("0+.", scripted)
        assert scripted.getvalue() == "1"

    def test_move_between_stacks(self) -> None:
        r"""= moves a value to the other stack; ~ switches the current stack."""
        assert run_and_capture("0=~.") == "0"

    def test_pointer_check(self) -> None:
        assert run_and_capture("0`0`+.") == "2"

    def test_truth_machine(self) -> None:
        assert run_and_capture('"0+.^!"^0?!0.') == "0"

    def test_duplicate(self) -> None:
        r"""^ copies the top without removing it, so it can be printed twice."""
        assert run_and_capture("0+^..") == "11"

    def test_decrement(self) -> None:
        r"""- subtracts one, where + adds it."""
        assert run_and_capture("0-.") == "-1"
        assert run_and_capture("0--.") == "-2"
        assert run_and_capture("0+-.") == "0"

    def test_pop_discards_the_top(self) -> None:
        r"""; drops the top value, leaving the one beneath it."""
        assert run_and_capture("0+0+;.") == "1"

    def test_reverse_turns_the_stack_over(self) -> None:
        r"""* reverses the current stack, so the bottom becomes the top."""
        assert run_and_capture("0+0*.") == "1"
        assert run_and_capture("0+0+*..") == "11"

    def test_backtick_pushes_the_stack_index(self) -> None:
        r"""` pushes which stack is *not* current -- 1 on the first, 0 on the."""
        assert run_and_capture("`.") == "1"
        assert run_and_capture("~`.") == "0"

    def test_move_targets_the_other_stack(self) -> None:
        r"""= puts the value on the stack that is not current."""
        assert run_and_capture("0+=~.") == "1"

    def test_move_targets_the_other_stack_from_either_side(self) -> None:
        r"""``=`` reads which stack is current; it does not always mean stack 1."""
        assert run_and_capture("~0+=~.") == "1"

    def test_switching_twice_returns_to_the_first_stack(self) -> None:
        r"""``~`` toggles the current stack rather than selecting the second."""
        assert run_and_capture("0+~~.") == "1"

    def test_output_on_empty_stack_halts(self) -> None:
        r"""Reading a value that is not there is an invalid operation."""
        for code in (".", ";", "^"):
            with pytest.raises(HaltError):
                run(code, IO())

    def test_eval_string_halts_on_non_string(self) -> None:
        r"""."""
        with pytest.raises(HaltError):
            run("0!", IO())

    def test_eval_string_evaluates_program(self) -> None:
        r"""."""
        assert run_and_capture('"0+."!') == "1"

    def test_arithmetic_on_string_halts(self) -> None:
        r"""+ on a non-numeric top is an invalid operation."""
        with pytest.raises(HaltError):
            run('"abc"+', IO())


class TestFrames:
    r"""``!`` runs on a frame stack rather than through Python recursion."""

    def test_a_nested_program_takes_a_step_per_command(self) -> None:
        r"""Entering ``!`` costs a step, and so does each command inside it."""
        state = _Machine('"0."!', ScriptedIO(""))
        steps = 0
        while not state.halted:
            state.step()
            steps += 1
        assert state.io.getvalue() == "0"
        # literal, !, then 0 and .
        assert steps > 2, "the nested program's commands are steps of their own"

    def test_the_frame_stack_deepens_inside_a_nested_program(self) -> None:
        r"""``ip`` reports the depth, which a bare cursor could not."""
        state = _Machine('"0."!', ScriptedIO(""))
        state.step()  # the literal.
        assert state.ip[0] == 1
        state.step()  # `!` pushes the nested program.
        assert state.ip[0] == 2, "the nested program is a frame of its own"

    def test_endless_recursion_is_proved_rather_than_crashing(self) -> None:
        r"""A self-referential program is decided by the ancestor check."""
        from esolangs.vm import run_until_halt_or_ancestor

        looping = _Machine('"0+.^!"^0+?!0.', ScriptedIO(""))
        assert run_until_halt_or_ancestor(looping) is False

        # A nested program that does.
        finite = _Machine('"0."!', ScriptedIO(""))
        assert run_until_halt_or_ancestor(finite) is True

    def test_the_entry_key_separates_frames_by_their_stacks(self) -> None:
        r"""Frames share one store, so the key has to carry it."""
        state = _Machine('"0."!', ScriptedIO(""))
        frame = ("0.", 0)
        before = state.frame_entry_key(frame)
        pushed = (*state.stk[state.ptr], 7)
        state.stk = (pushed, state.stk[1]) if state.ptr == 0 else (state.stk[0], pushed)
        assert state.frame_entry_key(frame) != before


class TestStepMachine:
    def test_the_empty_program_starts_halted(self) -> None:
        # `step` has no halted guard of.
        # which is what the VM's run.
        assert _Machine("", IO()).halted

    def test_snapshot_is_hashable_and_tracks_progress(self) -> None:
        state = _Machine("0+.", IO())
        before = state.snapshot()
        hash(before)  # must not raise.
        state.step()
        assert state.snapshot() != before
