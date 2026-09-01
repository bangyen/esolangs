"""Unit tests for the Eval interpreter."""

import io
from contextlib import redirect_stdout

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.stack_based.eval import State, run


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
        """A backtick inside stringmode becomes a double quote."""
        assert run_and_capture('"`".') == '"'

    def test_charmode(self) -> None:
        """' wraps the string in double quotes."""
        assert run_and_capture("'ab\".") == '"ab"'

    def test_a_literal_ends_at_the_first_quote_not_the_last(self) -> None:
        """Two literals in one program stay separate.

        Every other program here holds a single literal, where the closing
        quote is also the program's last one -- so ending at the first quote
        and ending at the last are the same position.  With a second literal
        after it they diverge: taking the last quote swallows the commands
        in between and returns them as one long string.
        """
        assert run_and_capture('"a"."b".') == "ab"

    def test_a_literal_advances_the_cursor_from_where_it_started(self) -> None:
        """A literal moves the cursor *on* by its length, not *to* it.

        Every other literal here is the program's first command, where the
        cursor starts at 0 and advancing by the length coincides with being
        set to it.  Placed later the two diverge, and setting the cursor
        rewinds it -- the prefix then runs again forever, so the assertion
        is on the index rather than on output that never arrives.
        """
        state = State(io=ScriptedIO(), sym='0+."a".')
        for _ in range(3):
            state.step()
        assert state.ind == 3

        state.step()  # the literal at index 3: past the closing quote
        assert state.ind == 6
        assert state.stk[state.ptr] == ["a"]

    def test_only_the_two_quotes_start_a_literal(self) -> None:
        """No other character opens stringmode -- the rest are commands or no-ops.

        The two quote forms share a branch, so they are a set, and a widened
        one would swallow a character that should have done something else.
        Pinning that with one chosen stand-in would only pin that stand-in,
        so this sweeps the printable range: every character outside the
        quotes and the command set must leave the stack alone.
        """
        commands = set("`^0+-.=;~*?!\"'")
        for char in map(chr, range(0x20, 0x7F)):
            if char in commands:
                continue
            state = State(io=ScriptedIO(), sym=char)
            state.step()
            assert state.stk == [[], []], f"{char!r} was not a no-op"
            assert state.ind == 1

    def test_output_goes_to_the_supplied_io(self) -> None:
        """``run`` writes through its ``io`` argument, not a fresh default one.

        ``run_and_capture`` redirects stdout and passes a plain ``IO``, so a
        machine built with the *default* ``IO`` prints to the same redirected
        stream and looks identical.  Handing in a ``ScriptedIO`` separates
        them: it collects what the program prints, and stays empty if the
        argument was dropped on the way through.
        """
        scripted = ScriptedIO("")
        run("0+.", scripted)
        assert scripted.getvalue() == "1"

    def test_move_between_stacks(self) -> None:
        """= moves a value to the other stack; ~ switches the current stack."""
        assert run_and_capture("0=~.") == "0"

    def test_pointer_check(self) -> None:
        assert run_and_capture("0`0`+.") == "2"

    def test_truth_machine(self) -> None:
        assert run_and_capture('"0+.^!"^0?!0.') == "0"

    def test_duplicate(self) -> None:
        """^ copies the top without removing it, so it can be printed twice.

        Nothing used ``^`` except the truth machine, where its result is
        consumed by ``!`` rather than shown -- so the command could have
        done nothing at all.
        """
        assert run_and_capture("0+^..") == "11"

    def test_decrement(self) -> None:
        """- subtracts one, where + adds it."""
        assert run_and_capture("0-.") == "-1"
        assert run_and_capture("0--.") == "-2"
        assert run_and_capture("0+-.") == "0"

    def test_pop_discards_the_top(self) -> None:
        """; drops the top value, leaving the one beneath it."""
        assert run_and_capture("0+0+;.") == "1"

    def test_reverse_turns_the_stack_over(self) -> None:
        """* reverses the current stack, so the bottom becomes the top."""
        assert run_and_capture("0+0*.") == "1"
        assert run_and_capture("0+0+*..") == "11"

    def test_backtick_pushes_the_stack_index(self) -> None:
        """` pushes which stack is *not* current -- 1 on the first, 0 on the
        second.

        ``test_pointer_check`` adds two of them together, where pushing the
        current index instead sums to 0 rather than 2 -- but nothing showed
        the value itself, or that it follows the switch.
        """
        assert run_and_capture("`.") == "1"
        assert run_and_capture("~`.") == "0"

    def test_move_targets_the_other_stack(self) -> None:
        """= puts the value on the stack that is not current.

        ``test_move_between_stacks`` moves a 0 and prints a 0, which the
        same program prints whether or not the move happened.  Moving a 1
        and finding it only after ``~`` shows where it went.
        """
        assert run_and_capture("0+=~.") == "1"

    def test_move_targets_the_other_stack_from_either_side(self) -> None:
        """``=`` reads which stack is current; it does not always mean stack 1.

        The test above moves only from stack 0, where "the other stack" and
        "stack 1" coincide.  Switching first makes the move go the other
        way, to stack 0 -- an index computed by adding rather than
        subtracting runs off the end of the pair instead.
        """
        assert run_and_capture("~0+=~.") == "1"

    def test_switching_twice_returns_to_the_first_stack(self) -> None:
        """``~`` toggles the current stack rather than selecting the second.

        Every other program switches at most once, starting from stack 0,
        where a toggle and an assignment to 1 agree.  Coming back is what
        separates them: the value pushed before the switches has to still
        be there afterwards.
        """
        assert run_and_capture("0+~~.") == "1"

    def test_output_on_empty_stack_halts(self) -> None:
        """Reading a value that is not there is an invalid operation."""
        for code in (".", ";", "^"):
            with pytest.raises(HaltError):
                run(code, IO())

    def test_eval_string_halts_on_non_string(self) -> None:
        """! on a non-string value is an invalid operation."""
        with pytest.raises(HaltError):
            run("0!", IO())

    def test_eval_string_evaluates_program(self) -> None:
        """! evaluates a pushed string as a program."""
        assert run_and_capture('"0+."!') == "1"

    def test_arithmetic_on_string_halts(self) -> None:
        """+ on a non-numeric top is an invalid operation."""
        with pytest.raises(HaltError):
            run('"abc"+', IO())


class TestFrames:
    """``!`` runs on a frame stack rather than through Python recursion."""

    def test_a_nested_program_takes_a_step_per_command(self) -> None:
        """Entering ``!`` costs a step, and so does each command inside it.

        Running the nested program to completion inside the caller's step
        made a program of any length cost one step, which hid it from the
        VM's step budget entirely.
        """
        state = State.of('"0."!', ScriptedIO(""))
        steps = 0
        while not state.halted:
            state.step()
            steps += 1
        assert state.io.getvalue() == "0"
        # literal, !, then 0 and . inside the frame, then two pops.
        assert steps > 2, "the nested program's commands are steps of their own"

    def test_the_frame_stack_deepens_inside_a_nested_program(self) -> None:
        """``ip`` reports the depth, which a bare cursor could not."""
        state = State.of('"0."!', ScriptedIO(""))
        state.step()  # the literal
        assert state.ip[0] == 1
        state.step()  # `!` pushes the nested program
        assert state.ip[0] == 2, "the nested program is a frame of its own"

    def test_endless_recursion_is_proved_rather_than_crashing(self) -> None:
        """A self-referential program is decided by the ancestor check.

        It used to run to completion inside one step and die with
        ``RecursionError``; nothing could see the recursion, because no
        intermediate state ever reached the machine's surface.
        """
        from esolangs.vm import run_until_halt_or_ancestor

        looping = State.of('"0+.^!"^0+?!0.', ScriptedIO(""))
        assert run_until_halt_or_ancestor(looping) is False

        # A nested program that does terminate still reports as halting.
        finite = State.of('"0."!', ScriptedIO(""))
        assert run_until_halt_or_ancestor(finite) is True

    def test_the_entry_key_separates_frames_by_their_stacks(self) -> None:
        """Frames share one store, so the key has to carry it.

        Two frames running the same text at the same cursor go on to do
        different things when the values beneath them differ, so a key of
        text and cursor alone would call an advancing recursion a repeat.
        """
        state = State.of('"0."!', ScriptedIO(""))
        frame = ("0.", 0)
        before = state.frame_entry_key(frame)
        state.stk[state.ptr].append(7)
        assert state.frame_entry_key(frame) != before


class TestStepMachine:
    def test_the_empty_program_starts_halted(self) -> None:
        # `step` has no halted guard of its own -- the caller checks first,
        # which is what the VM's run loop does.
        assert State(io=IO(), sym="").halted

    def test_snapshot_is_hashable_and_tracks_progress(self) -> None:
        state = State(io=IO(), sym="0+.")
        before = state.snapshot()
        hash(before)  # must not raise
        state.step()
        assert state.snapshot() != before
