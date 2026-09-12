r"""Unit tests for the Modulous interpreter."""

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
        r"""``PSH`` needs one of ``INT``/``STR``/``VAR`` to know what to push."""
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
        r"""A 0 input prints 0 and halts."""
        program = (
            "[INP INT][DUP][JMP F 4 IF 0][PRT INT][PSH INT 1]"
            "[JMP B 3 NIF 0][PSH INT 0][PRT INT][END]"
        )
        assert run_and_capture(program, inputs=["0"]) == "0"

    def test_input_string(self) -> None:
        assert run_and_capture("[INP][PRT][PRT][END]", inputs=["AB"]) == "AB"

    def test_empty_int_read_pushes_nothing(self) -> None:
        r"""``INP INT`` on a blank line leaves the stack alone."""
        assert run_and_capture("[PSH INT 7][INP INT][PRT INT][END]", inputs=[""]) == "7"

    def test_swap(self) -> None:
        assert (
            run_and_capture("[PSH INT 1][PSH INT 2][SWP][PRT INT][PRT INT][END]")
            == "12"
        )

    def test_jump_forward(self) -> None:
        r"""JMP F skips a module."""
        assert run_and_capture("[PSH INT 5][JMP F 1][PRT INT][END]") == "5"

    def test_conditional_jump(self) -> None:
        r"""JMP ."""
        assert run_and_capture("[PSH INT 5][JMP F 1 IF 5][PRT INT][END]") == "5"

    def test_conditional_jump_nif(self) -> None:
        r"""JMP ."""
        assert run_and_capture("[PSH INT 5][JMP F 1 NIF 5][PRT INT][END]") == "5"

    def test_conditional_jump_nif_takes_the_jump(self) -> None:
        r"""NIF jumps when the top does *not* match, which is its whole point."""
        program = "[PSH INT 5][JMP F 2 NIF 9][PRT INT][PSH INT 7][PRT INT][END]"
        assert run_and_capture(program) == "7"

    def test_jump_compares_zero_on_an_empty_stack(self) -> None:
        r"""With nothing pushed the compared value is 0, not some other."""
        program = "[JMP F 2 NIF 1][PSH INT 3][PRT INT][PSH INT 8][PRT INT][END]"
        with pytest.raises(HaltError):
            run_and_capture(program)

    def test_backward_jump(self) -> None:
        r"""JMP B jumps backwards, eventually landing on END."""
        assert run_and_capture("[JMP B 1][END]") == ""

    def test_forward_jump_is_relative_and_lands_past_the_skip(self) -> None:
        r"""``JMP F n`` moves ``n`` modules on from the jump, not to module n."""
        assert run_and_capture("[JMP F 2][PSH INT 7][PSH INT 8][PRT INT][END]") == "8"
        assert run_and_capture("[JMP F 1][PSH INT 7][PRT INT][END]") == "7"

    def test_backward_jump_distance_is_counted_from_the_jump(self) -> None:
        r"""``JMP B n`` lands ``n`` modules back, making a fixed-size loop."""
        from esolangs.interpreters.stack_based.modulous import _Machine

        io = ScriptedIO()
        machine = _Machine("[PSH INT 9][PRT INT][JMP B 2][END]", io)
        for _ in range(12):
            if machine.halted:
                break
            machine.step()
        assert io.getvalue() == "9999"

    def test_pop(self) -> None:
        r"""POP removes the top of the stack."""
        assert run_and_capture("[PSH INT 5][POP][PSH INT 7][PRT INT][END]") == "7"

    def test_pop_leaves_the_rest_of_the_stack(self) -> None:
        r"""It removes one value, not all but the bottom one."""
        staged = "[PSH INT 1][PSH INT 2][PSH INT 3]"
        assert run_and_capture(f"{staged}[POP][PRT INT][END]") == "2"
        assert run_and_capture(f"{staged}[POP][POP][PRT INT][END]") == "1"

    def test_reset(self) -> None:
        r"""RST restarts from the first module, re-reading input."""
        # After RST the pointer returns.
        # line is read; then JMP F 2 IF.
        assert (
            run_and_capture(
                "[INP INT][JMP F 2 IF 0][RST][PRT INT][END]", inputs=["5", "0"]
            )
            == "0"
        )

    def test_push_variable(self) -> None:
        r"""``[PSH VARn]`` stores the top of the stack in a variable."""
        assert run_and_capture("[PSH INT 7][PSH VAR1][PRT VAR1 INT][END]") == "7"

    def test_random(self) -> None:
        r"""RND pushes a random value below the given bound."""
        assert run_and_capture("[RND 1][PRT INT][END]") == "0"

    def test_variable_add(self) -> None:
        assert run_and_capture("[VAR1+3][PRT VAR1 INT][END]") == "3"

    def test_variable_subtract(self) -> None:
        assert run_and_capture("[VAR1-3][PRT VAR1 INT][END]") == "-3"

    def test_variable_arithmetic_accumulates(self) -> None:
        r"""``VARn+k`` adds to the variable rather than replacing it."""
        assert run_and_capture("[VAR1+2][VAR1+3][PRT VAR1 INT][END]") == "5"
        assert run_and_capture("[VAR1+2][VAR1-1][PRT VAR1 INT][END]") == "1"

    def test_variables_are_var1_through_var4(self) -> None:
        r"""Four variables exist, named from 1 -- not from 0, and not five."""
        for name in ("VAR1", "VAR4"):
            assert run_and_capture(f"[{name}+3][PRT {name} INT][END]") == "3"
        for name in ("VAR0", "VAR5"):
            with pytest.raises(HaltError):
                run(f"[{name}+3][PRT {name} INT][END]", IO())

    def test_add_targets_the_top_of_the_stack(self) -> None:
        r"""``ADD`` changes the top cell, leaving what is under it alone."""
        assert (
            run_and_capture(
                "[PSH INT 1][PSH INT 2][PSH INT 3][ADD 4]"
                "[PRT INT][PRT INT][PRT INT][END]"
            )
            == "721"
        )

    def test_string_and_input_pushes_keep_the_stack_under_them(self) -> None:
        r"""``PSH STR`` and ``INP`` extend the stack rather than replacing it."""
        assert run_and_capture('[PSH INT 65][PSH STR "B"][PRT][PRT][END]') == "BA"
        assert run_and_capture("[PSH INT 65][INP][PRT][PRT][END]", inputs=["B"]) == "BA"

    def test_add_on_empty_stack_halts(self) -> None:
        r"""Arithmetic on an empty stack is an invalid operation."""
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
        r"""Storing into an undeclared variable is invalid, as reading one is."""
        with pytest.raises(HaltError):
            run("[PSH INT 7][PSH VAR9]", IO())

    def test_push_variable_keyword_spelling_halts(self) -> None:
        r"""``[PSH VAR VAR1]`` is not the syntax and does not quietly store."""
        with pytest.raises(HaltError):
            run("[PSH INT 7][PSH VAR VAR1]", IO())

    def test_subtract_undefined_variable_halts(self) -> None:
        with pytest.raises(HaltError):
            run("[VAR9-3]", IO())

    def test_random_zero_bound_halts(self) -> None:
        with pytest.raises(HaltError):
            run("[RND 0]", IO())

    def test_missing_jump_operand_rejected(self) -> None:
        r"""A command missing a required operand is malformed."""
        with pytest.raises(ValueError, match="missing operand"):
            run("[JMP]", IO())

    def test_missing_operand_message_quotes_the_whole_command(self) -> None:
        r"""The message echoes the command with its tokens spaced normally."""
        with raises_message(ValueError, "missing operand in JMP F"):
            run("[JMP F]", IO())

    def test_empty_block_is_a_noop(self) -> None:
        r"""An empty ``[]`` block has no command and is skipped, not crashed on."""
        run("[]", IO())
        run("[ ]\n[]", IO())

    def test_an_unknown_command_is_refused(self) -> None:
        r"""This test used to run ``[p 5]`` and assert it was a no-op."""
        with pytest.raises(ValueError, match="is not a Modulous command"):
            run("[p 5]", IO())
        with pytest.raises(ValueError, match="PRTINT"):
            run('[PSH STR "x"][PRTINT][END]', IO())

    def test_text_outside_a_command_is_refused(self) -> None:
        r"""``findall`` dropped it, so an unbalanced bracket ran half a program."""
        with pytest.raises(ValueError, match="outside any"):
            run("[PSH INT 1[END]", IO())
        with pytest.raises(ValueError, match="outside any"):
            run("[END] trailing junk", IO())

    def test_whitespace_between_commands_is_still_fine(self) -> None:
        r"""The refusal must not reject the layout every program uses."""
        run("[PSH INT 1]\n\n  [POP]\t[END]", IO())

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
        from esolangs.interpreters.stack_based.modulous import _Machine

        # `step` has no halted guard of.
        # which is what the VM's run.
        assert _Machine("", IO()).halted

    def test_snapshot_is_hashable_and_tracks_progress(self) -> None:
        from esolangs.interpreters.stack_based.modulous import _Machine

        state = _Machine("[PSH INT 5][PRT INT][END]", IO())
        before = state.snapshot()
        hash(before)  # must not raise.
        state.step()
        assert state.snapshot() != before
