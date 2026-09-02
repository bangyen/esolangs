"""Unit tests for the Modulous interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.stack_based.modulous import run
from tests.interpreters.runner import run_program
from tests.raises import raises_message


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


class TestModulous:
    def test_push_print_int(self) -> None:
        assert run_and_capture("[PSH INT 5][PRT INT][END]") == "5"

    def test_push_print_string(self) -> None:
        assert run_and_capture('[PSH STR "A"][PRT][END]') == "A"

    def test_push_string_then_pop(self) -> None:
        assert run_and_capture('[PSH STR "AB"][PRT][PRT][END]') == "AB"

    def test_push_without_a_type_pushes_nothing(self) -> None:
        """``PSH`` needs one of ``INT``/``STR``/``VAR`` to know what to push.

        Without one it is a no-op rather than an error, so a value pushed
        before it is still on top afterwards -- printing gives the earlier
        value, not the typeless push's operand.
        """
        assert run_and_capture("[PSH INT 5][PSH 9][PRT INT][END]") == "5"
        assert run_and_capture("[PSH 5][END]") == ""

    def test_add(self) -> None:
        assert run_and_capture("[PSH INT 5][PSH INT 2][ADD 3][PRT INT][END]") == "5"

    def test_subtract(self) -> None:
        assert run_and_capture("[PSH INT 8][SUB 3][PRT INT][END]") == "5"

    def test_duplicate(self) -> None:
        assert run_and_capture("[PSH INT 4][DUP][PRT INT][PRT INT][END]") == "44"

    def test_input(self) -> None:
        assert run_and_capture("[INP INT][PRT INT][END]", inputs=["42"]) == "42"

    def test_truth_machine_zero(self) -> None:
        """A 0 input prints 0 and halts.

        The 1 branch loops forever by definition, so only the terminating
        branch is exercised.
        """
        program = (
            "[INP INT][DUP][JMP F 4 IF 0][PRT INT][PSH INT 1]"
            "[JMP B 3 NIF 0][PSH INT 0][PRT INT][END]"
        )
        assert run_and_capture(program, inputs=["0"]) == "0"

    def test_input_string(self) -> None:
        assert run_and_capture("[INP][PRT][PRT][END]", inputs=["AB"]) == "AB"

    def test_empty_int_read_pushes_nothing(self) -> None:
        """``INP INT`` on a blank line leaves the stack alone.

        The bare form would push the line's characters, and an empty line
        has none; ``INT`` has no number to parse either, so it pushes
        nothing rather than a zero.  Printing afterwards therefore gives
        the value pushed *before* the read.
        """
        assert run_and_capture("[PSH INT 7][INP INT][PRT INT][END]", inputs=[""]) == "7"

    def test_swap(self) -> None:
        assert (
            run_and_capture("[PSH INT 1][PSH INT 2][SWP][PRT INT][PRT INT][END]")
            == "12"
        )

    def test_jump_forward(self) -> None:
        """JMP F skips a module."""
        assert run_and_capture("[PSH INT 5][JMP F 1][PRT INT][END]") == "5"

    def test_conditional_jump(self) -> None:
        """JMP ... IF jumps only when the top matches."""
        assert run_and_capture("[PSH INT 5][JMP F 1 IF 5][PRT INT][END]") == "5"

    def test_conditional_jump_nif(self) -> None:
        """JMP ... NIF jumps only when the top does not match."""
        assert run_and_capture("[PSH INT 5][JMP F 1 NIF 5][PRT INT][END]") == "5"

    def test_conditional_jump_nif_takes_the_jump(self) -> None:
        """NIF jumps when the top does *not* match, which is its whole point.

        ``test_conditional_jump_nif`` compares 5 against 5, so the condition
        is false and no jump happens -- the same output a NIF that never
        jumped, or one whose comparison was inverted, would give.  A
        mismatched operand makes it jump, and a distance of two lands
        somewhere the fall-through does not.
        """
        program = "[PSH INT 5][JMP F 2 NIF 9][PRT INT][PSH INT 7][PRT INT][END]"
        assert run_and_capture(program) == "7"

    def test_jump_compares_zero_on_an_empty_stack(self) -> None:
        """With nothing pushed the compared value is 0, not some other
        default: ``NIF 1`` therefore jumps, skipping the push it would
        otherwise print."""
        program = "[JMP F 2 NIF 1][PSH INT 3][PRT INT][PSH INT 8][PRT INT][END]"
        with pytest.raises(HaltError):
            run_and_capture(program)

    def test_backward_jump(self) -> None:
        """JMP B jumps backwards, eventually landing on END."""
        assert run_and_capture("[JMP B 1][END]") == ""

    def test_forward_jump_is_relative_and_lands_past_the_skip(self) -> None:
        """``JMP F n`` moves ``n`` modules on from the jump, not to module n.

        ``test_jump_forward`` jumps from module 1 by 1, where a relative
        move and an absolute one land in the same place, so neither the
        base nor the distance was pinned.  Here the jump is the *first*
        module and skips two: an absolute jump, or one that adds a
        different constant, lands on a different push and prints its value
        instead.
        """
        assert run_and_capture("[JMP F 2][PSH INT 7][PSH INT 8][PRT INT][END]") == "8"
        assert run_and_capture("[JMP F 1][PSH INT 7][PRT INT][END]") == "7"

    def test_backward_jump_distance_is_counted_from_the_jump(self) -> None:
        """``JMP B n`` lands ``n`` modules back, making a fixed-size loop.

        ``test_backward_jump`` jumps back one from module 0, which lands on
        ``END`` whatever constant the arithmetic uses.  This loops over a
        print: three modules per lap, one character each.  A backward jump
        of a different width takes a longer or shorter lap and prints a
        different number of characters in the same budget.

        The loop never ends, so this steps a fixed count rather than
        running it.
        """
        import re

        from esolangs.interpreters.stack_based.modulous import State

        io = ScriptedIO()
        machine = State(var={f"VAR{k}": 0 for k in range(1, 5)}, io=io)
        reg = re.compile(r'\[([^\[\]"]*("[^"]*")?)]')
        machine.tokens = [
            k[0] for k in reg.findall("[PSH INT 9][PRT INT][JMP B 2][END]")
        ]
        for _ in range(12):
            if machine.halted:
                break
            machine.step()
        assert io.getvalue() == "9999"

    def test_pop(self) -> None:
        """POP removes the top of the stack."""
        assert run_and_capture("[PSH INT 5][POP][PSH INT 7][PRT INT][END]") == "7"

    def test_reset(self) -> None:
        """RST restarts from the first module, re-reading input."""
        # After RST the pointer returns to the start, so the second input
        # line is read; then JMP F 2 IF 0 jumps over RST to PRT/END.
        assert (
            run_and_capture(
                "[INP INT][JMP F 2 IF 0][RST][PRT INT][END]", inputs=["5", "0"]
            )
            == "0"
        )

    def test_push_variable(self) -> None:
        """``[PSH VARn]`` stores the top of the stack in a variable."""
        assert run_and_capture("[PSH INT 7][PSH VAR1][PRT VAR1 INT][END]") == "7"

    def test_random(self) -> None:
        """RND pushes a random value below the given bound."""
        assert run_and_capture("[RND 1][PRT INT][END]") == "0"

    def test_variable_add(self) -> None:
        assert run_and_capture("[VAR1+3][PRT VAR1 INT][END]") == "3"

    def test_variable_subtract(self) -> None:
        assert run_and_capture("[VAR1-3][PRT VAR1 INT][END]") == "-3"

    def test_variable_arithmetic_accumulates(self) -> None:
        """``VARn+k`` adds to the variable rather than replacing it.

        Both cases above touch a variable once, starting from zero -- where
        adding and assigning give the same answer.  Two operations tell
        them apart, and mixing a ``+`` with a ``-`` pins each arm.
        """
        assert run_and_capture("[VAR1+2][VAR1+3][PRT VAR1 INT][END]") == "5"
        assert run_and_capture("[VAR1+2][VAR1-1][PRT VAR1 INT][END]") == "1"

    def test_variables_are_var1_through_var4(self) -> None:
        """Four variables exist, named from 1 -- not from 0, and not five.

        Every variable test names ``VAR1``, which exists under any of the
        plausible ranges, so the ends were never pinned.  An undeclared
        name halts, so the two names just outside the range say where it
        stops as clearly as the two inside say where it runs.
        """
        for name in ("VAR1", "VAR4"):
            assert run_and_capture(f"[{name}+3][PRT {name} INT][END]") == "3"
        for name in ("VAR0", "VAR5"):
            with pytest.raises(HaltError):
                run(f"[{name}+3][PRT {name} INT][END]", IO())

    def test_add_targets_the_top_of_the_stack(self) -> None:
        """``ADD`` changes the top cell, leaving what is under it alone.

        Indexing from the far end has to miss by more than the stack is
        deep to be visible: on two values ``stk[1]`` and ``stk[-1]`` are the
        same cell.  Three separate them -- the top 3 becomes 7, while the 2
        in the middle (which ``stk[1]`` would have hit) stays put.
        """
        assert (
            run_and_capture(
                "[PSH INT 1][PSH INT 2][PSH INT 3][ADD 4]"
                "[PRT INT][PRT INT][PRT INT][END]"
            )
            == "721"
        )

    def test_string_and_input_pushes_keep_the_stack_under_them(self) -> None:
        """``PSH STR`` and ``INP`` extend the stack rather than replacing it.

        Both build a list of character codes and add it to the stack; an
        assignment in place of that addition throws away everything already
        pushed, which no existing case would notice because each starts
        from an empty stack.  Pushing an ``A`` underneath makes the
        difference the trailing character of the output.
        """
        assert run_and_capture('[PSH INT 65][PSH STR "B"][PRT][PRT][END]') == "BA"
        assert run_and_capture("[PSH INT 65][INP][PRT][PRT][END]", inputs=["B"]) == "BA"

    def test_add_on_empty_stack_halts(self) -> None:
        """Arithmetic on an empty stack is an invalid operation."""
        with pytest.raises(HaltError):
            run("[ADD 1]", IO())

    def test_sub_on_empty_stack_halts(self) -> None:
        with pytest.raises(HaltError):
            run("[SUB 1]", IO())

    def test_pop_on_empty_stack_halts(self) -> None:
        with pytest.raises(HaltError):
            run("[POP]", IO())

    def test_swap_on_short_stack_halts(self) -> None:
        with pytest.raises(HaltError):
            run("[SWP]", IO())

    def test_dup_on_empty_stack_halts(self) -> None:
        with pytest.raises(HaltError):
            run("[DUP]", IO())

    def test_print_on_empty_stack_halts(self) -> None:
        with pytest.raises(HaltError):
            run("[PRT INT]", IO())

    def test_print_undefined_variable_halts(self) -> None:
        with pytest.raises(HaltError):
            run("[PRT VAR9 INT]", IO())

    def test_arithmetic_undefined_variable_halts(self) -> None:
        with pytest.raises(HaltError):
            run("[VAR9+3]", IO())

    def test_push_undefined_variable_halts(self) -> None:
        """Storing into an undeclared variable is invalid, as reading one is.

        ``PRT`` and the ``VARn+k`` arithmetic both halt on a name that was
        never declared; the store used to be the one variable op that did
        not check, so it created the name instead.
        """
        with pytest.raises(HaltError):
            run("[PSH INT 7][PSH VAR9]", IO())

    def test_push_variable_keyword_spelling_halts(self) -> None:
        """``[PSH VAR VAR1]`` is not the syntax and does not quietly store.

        The store names its variable directly (``[PSH VAR1]``), so the
        keyword spelling names a variable called ``VAR`` -- which does not
        exist.  It used to be accepted, creating ``VAR`` and leaving the
        ``VAR1`` the program meant untouched: a silent no-op that made the
        stored value simply disappear.
        """
        with pytest.raises(HaltError):
            run("[PSH INT 7][PSH VAR VAR1]", IO())

    def test_subtract_undefined_variable_halts(self) -> None:
        with pytest.raises(HaltError):
            run("[VAR9-3]", IO())

    def test_random_zero_bound_halts(self) -> None:
        with pytest.raises(HaltError):
            run("[RND 0]", IO())

    def test_missing_jump_operand_rejected(self) -> None:
        """A command missing a required operand is malformed."""
        with pytest.raises(ValueError, match="missing operand"):
            run("[JMP]", IO())

    def test_missing_operand_message_quotes_the_whole_command(self) -> None:
        """The message echoes the command with its tokens spaced normally.

        ``[JMP]`` is a single token, so it reads the same however the parts
        are joined -- the separator only shows once there are two of them.
        ``match=`` would not see it either way, being a substring search,
        so this asserts the message entire.
        """
        with raises_message(ValueError, "missing operand in JMP F"):
            run("[JMP F]", IO())

    def test_empty_block_is_a_noop(self) -> None:
        """An empty ``[]`` block has no command and is skipped, not crashed on."""
        run("[]", IO())
        run("[ ]\n[p 5]", IO())

    def test_missing_add_operand_rejected(self) -> None:
        with pytest.raises(ValueError, match="missing operand"):
            run("[ADD]", IO())

    def test_missing_push_operand_rejected(self) -> None:
        with pytest.raises(ValueError, match="missing operand"):
            run("[PSH INT]", IO())

    def test_missing_random_operand_rejected(self) -> None:
        with pytest.raises(ValueError, match="missing operand"):
            run("[RND]", IO())


class TestStepMachine:
    def test_a_token_less_state_starts_halted(self) -> None:
        from esolangs.interpreters.stack_based.modulous import State

        # `step` has no halted guard of its own -- the caller checks first,
        # which is what the VM's run loop does.
        assert State(io=IO()).halted

    def test_snapshot_is_hashable_and_tracks_progress(self) -> None:
        from esolangs.interpreters.stack_based.modulous import State

        state = State(io=IO())
        state.tokens = ["PSH INT 5", "PRT INT", "END"]
        before = state.snapshot()
        hash(before)  # must not raise
        state.step()
        assert state.snapshot() != before
