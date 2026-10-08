"""Unit tests for the Eval interpreter."""

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
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            pytest.param('"Hello, World!".', "Hello, World!", id="hello_world"),
            # A backtick inside stringmode becomes a double quote.
            pytest.param('"`".', '"', id="stringmode_backtick"),
            # ' wraps the string in double quotes.
            pytest.param("'ab\".", '"ab"', id="charmode"),
            # Two literals in one program stay separate.
            pytest.param(
                '"a"."b".', "ab", id="a_literal_ends_at_the_first_quote_not_the_last"
            ),
            # = moves a value to the other stack; ~ switches the current stack.
            pytest.param("0=~.", "0", id="move_between_stacks"),
            # ! evaluates a pushed string as a program.
            pytest.param('"0+."!', "1", id="eval_string_evaluates_program"),
        ],
    )
    def test_output(self, code: str, expected: str) -> None:
        assert run_and_capture(code) == expected

    def test_only_the_two_quotes_start_a_literal(self) -> None:
        """No other character opens stringmode -- the rest are commands or no-ops."""
        commands = set("`^0+-.=;~*?!\"'")
        for char in map(chr, range(0x20, 0x7F)):
            if char in commands:
                continue
            state = _Machine(char, ScriptedIO())
            state.step()
            assert state.stk == ((), ()), f"{char!r} was not a no-op"
            assert state.ind == 1

    def test_reverse_turns_the_stack_over(self) -> None:
        """* reverses the current stack, so the bottom becomes the top."""
        assert run_and_capture("0+0*.") == "1"
        assert run_and_capture("0+0+*..") == "11"

    def test_backtick_pushes_the_stack_index(self) -> None:
        """` pushes which stack is *not* current -- 1 on the first, 0 on the
        second.
        """
        assert run_and_capture("`.") == "1"
        assert run_and_capture("~`.") == "0"

    def test_output_on_empty_stack_halts(self) -> None:
        """Reading a value that is not there is an invalid operation."""
        for code in (".", ";", "^"):
            with pytest.raises(HaltError):
                run(code, IO())

    def test_eval_string_halts_on_non_string(self) -> None:
        """! on a non-string value is an invalid operation."""
        with pytest.raises(HaltError):
            run("0!", IO())

    def test_arithmetic_on_string_halts(self) -> None:
        """+ on a non-numeric top is an invalid operation."""
        with pytest.raises(HaltError):
            run('"abc"+', IO())


class TestFrames:
    """``!`` runs on a frame stack rather than through Python recursion."""

    def test_the_frame_stack_deepens_inside_a_nested_program(self) -> None:
        """``ip`` reports the depth, which a bare cursor could not."""
        state = _Machine('"0."!', ScriptedIO(""))
        state.step()  # the literal
        assert state.ip[0] == 1
        state.step()  # `!` pushes the nested program
        assert state.ip[0] == 2, "the nested program is a frame of its own"

    def test_endless_recursion_is_proved_rather_than_crashing(self) -> None:
        """A self-referential program is decided by the ancestor check."""
        from esolangs.vm import run_until_halt_or_ancestor

        looping = _Machine('"0+.^!"^0+?!0.', ScriptedIO(""))
        assert run_until_halt_or_ancestor(looping) is False

        # A nested program that does terminate still reports as halting.
        finite = _Machine('"0."!', ScriptedIO(""))
        assert run_until_halt_or_ancestor(finite) is True

    def test_the_entry_key_separates_frames_by_their_stacks(self) -> None:
        """Frames share one store, so the key has to carry it."""
        state = _Machine('"0."!', ScriptedIO(""))
        frame = ("0.", 0)
        before = state.frame_entry_key(frame)
        pushed = (*state.stk[state.ptr], 7)
        state.stk = (pushed, state.stk[1]) if state.ptr == 0 else (state.stk[0], pushed)
        assert state.frame_entry_key(frame) != before


class TestStepMachine:
    def test_the_empty_program_starts_halted(self) -> None:
        # `step` has no halted guard of its own -- the caller checks first,
        # which is what the VM's run loop does.
        assert _Machine("", IO()).halted

    def test_snapshot_is_hashable_and_tracks_progress(self) -> None:
        state = _Machine("0+.", IO())
        before = state.snapshot()
        hash(before)  # must not raise
        state.step()
        assert state.snapshot() != before
