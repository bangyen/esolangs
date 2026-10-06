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

    def test_push_without_a_type_is_refused(self) -> None:
        """``PSH`` needs one of ``INT``/``STR``/``VARn`` to know what to push."""
        with pytest.raises(ValueError, match="invalid PSH operand '9'"):
            run("[PSH INT 5][PSH 9][PRT INT][END]", IO())

    def test_push_dispatches_on_its_type_word(self) -> None:
        """``INT`` inside a quoted string is data, not the push type."""
        assert run_and_capture('[PSH STR "INT"][PRT STR][END]') == "I"

    def test_a_space_after_the_quoted_string_is_inside_the_command(self) -> None:
        """``[PSH STR "A" ]`` is one command; it was refused as stray text."""
        assert run_and_capture('[PSH STR "A" ][PRT STR][END]') == "A"

    def test_input(self) -> None:
        assert run_and_capture("[INP INT][PRT INT][END]", inputs=["42"]) == "42"

    def test_truth_machine_zero(self) -> None:
        """A 0 input prints 0 and halts."""
        program = (
            "[INP INT][DUP][JMP F 4 IF 0][PRT INT][PSH INT 1]"
            "[JMP B 3 NIF 0][PSH INT 0][PRT INT][END]"
        )
        assert run_and_capture(program, inputs=["0"]) == "0"

    def test_input_string(self) -> None:
        assert run_and_capture("[INP][PRT][PRT][END]", inputs=["AB"]) == "AB"
        assert run_and_capture("[INP][PRT][PRT][PRT][END]", inputs=["A B"]) == "A B"

    def test_integer_input_skips_blank_lines(self) -> None:
        """Integer input skips blank lines before reading a token."""
        assert run_and_capture("[INP INT][PRT INT][END]", inputs=["", "7"]) == "7"

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
        """NIF jumps when the top does *not* match, which is its whole point."""
        program = "[PSH INT 5][JMP F 2 NIF 9][PRT INT][PSH INT 7][PRT INT][END]"
        assert run_and_capture(program) == "7"

    def test_jump_compares_zero_on_an_empty_stack(self) -> None:
        """With nothing pushed the compared value is 0, not some other
        default: ``NIF 1`` therefore jumps, skipping the push it would
        otherwise print.
        """
        program = "[JMP F 2 NIF 1][PSH INT 3][PRT INT][PSH INT 8][PRT INT][END]"
        with pytest.raises(HaltError):
            run_and_capture(program)

    def test_backward_jump(self) -> None:
        """JMP B jumps backwards, eventually landing on END."""
        assert run_and_capture("[JMP B 1][END]") == ""

    def test_forward_jump_is_relative_and_lands_past_the_skip(self) -> None:
        """``JMP F n`` moves ``n`` modules on from the jump, not to module n."""
        assert run_and_capture("[JMP F 2][PSH INT 7][PSH INT 8][PRT INT][END]") == "8"
        assert run_and_capture("[JMP F 1][PSH INT 7][PRT INT][END]") == "7"

    def test_backward_jump_distance_is_counted_from_the_jump(self) -> None:
        """``JMP B n`` lands ``n`` modules back, making a fixed-size loop."""
        from esolangs.interpreters.stack_based.modulous import _Machine

        io = ScriptedIO()
        machine = _Machine("[PSH INT 9][PRT INT][JMP B 2][END]", io)
        for _ in range(12):
            if machine.halted:
                break
            machine.step()
        assert io.getvalue() == "9999"

    def test_pop(self) -> None:
        """POP removes the top of the stack."""
        assert run_and_capture("[PSH INT 5][POP][PSH INT 7][PRT INT][END]") == "7"

    def test_pop_leaves_the_rest_of_the_stack(self) -> None:
        """It removes one value, not all but the bottom one."""
        staged = "[PSH INT 1][PSH INT 2][PSH INT 3]"
        assert run_and_capture(f"{staged}[POP][PRT INT][END]") == "2"
        assert run_and_capture(f"{staged}[POP][POP][PRT INT][END]") == "1"

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

    def test_variable_arithmetic_takes_a_signed_operand(self) -> None:
        """The first sign is the operator; the rest is the number (b9623084)."""
        assert run_and_capture("[VAR1--2][PRT VAR1 INT][END]") == "2"
        assert run_and_capture("[VAR1-+2][PRT VAR1 INT][END]") == "-2"

    def test_variable_arithmetic_accumulates(self) -> None:
        """``VARn+k`` adds to the variable rather than replacing it."""
        assert run_and_capture("[VAR1+2][VAR1+3][PRT VAR1 INT][END]") == "5"
        assert run_and_capture("[VAR1+2][VAR1-1][PRT VAR1 INT][END]") == "1"

    def test_variables_are_var1_through_var4(self) -> None:
        """Four variables exist, named from 1 -- not from 0, and not five."""
        for name in ("VAR1", "VAR4"):
            assert run_and_capture(f"[{name}+3][PRT {name} INT][END]") == "3"
        for name in ("VAR0", "VAR5"):
            with pytest.raises(HaltError):
                run(f"[{name}+3][PRT {name} INT][END]", IO())

    def test_add_targets_the_top_of_the_stack(self) -> None:
        """``ADD`` changes the top cell, leaving what is under it alone."""
        assert (
            run_and_capture(
                "[PSH INT 1][PSH INT 2][PSH INT 3][ADD 4]"
                "[PRT INT][PRT INT][PRT INT][END]"
            )
            == "721"
        )

    def test_string_and_input_pushes_keep_the_stack_under_them(self) -> None:
        """``PSH STR`` and ``INP`` extend the stack rather than replacing it."""
        assert run_and_capture('[PSH INT 65][PSH STR "B"][PRT][PRT][END]') == "BA"
        assert run_and_capture("[PSH INT 65][INP][PRT][PRT][END]", inputs=["B"]) == "BA"

    def test_add_on_empty_stack_halts(self) -> None:
        """Arithmetic on an empty stack is an invalid operation."""
        with pytest.raises(HaltError):
            run("[ADD 1]", IO())

    def test_swap_on_short_stack_halts(self) -> None:
        with pytest.raises(HaltError):
            run("[SWP]", IO())

    def test_print_on_empty_stack_halts(self) -> None:
        with pytest.raises(HaltError):
            run("[PRT INT]", IO())

    def test_print_undefined_variable_halts(self) -> None:
        with pytest.raises(HaltError):
            run("[PRT VAR9 INT]", IO())

    def test_push_undefined_variable_halts(self) -> None:
        """Storing into an undeclared variable is invalid, as reading one is."""
        with pytest.raises(HaltError):
            run("[PSH INT 7][PSH VAR9]", IO())

    def test_push_variable_keyword_spelling_halts(self) -> None:
        """``[PSH VAR VAR1]`` is not the syntax and does not quietly store."""
        with pytest.raises(HaltError):
            run("[PSH INT 7][PSH VAR VAR1]", IO())

    def test_random_zero_bound_halts(self) -> None:
        with pytest.raises(HaltError):
            run("[RND 0]", IO())

    def test_missing_jump_operand_rejected(self) -> None:
        """A command missing a required operand is malformed."""
        with pytest.raises(ValueError, match="missing operand"):
            run("[JMP]", IO())

    def test_push_string_without_quotes_is_rejected(self) -> None:
        """``[PSH STR hello]`` has no quoted section to push."""
        with raises_message(
            ValueError,
            'missing quoted string in PSH STR hello; expected [PSH STR "text"]',
        ):
            run("[PSH STR hello]", IO())

    def test_missing_operand_message_quotes_the_whole_command(self) -> None:
        """The message echoes the command with its tokens spaced normally."""
        with raises_message(ValueError, "missing operand in JMP F"):
            run("[JMP F]", IO())

    def test_empty_block_is_a_noop(self) -> None:
        """An empty ``[]`` block has no command and is skipped, not crashed on."""
        run("[]", IO())
        run("[ ]\n[]", IO())

    def test_an_unknown_command_is_refused(self) -> None:
        """This test used to run ``[p 5]`` and assert it was a no-op."""
        with pytest.raises(ValueError, match="is not a Modulous command"):
            run("[p 5]", IO())
        with pytest.raises(ValueError, match="PRTINT"):
            run('[PSH STR "x"][PRTINT][END]', IO())

    @pytest.mark.parametrize(
        ("source", "hint"),
        [("[PHS INT 5]", "PSH"), ("[PRTT INT]", "PRT")],
    )
    def test_unknown_command_suggests_one_match(self, source: str, hint: str) -> None:
        with pytest.raises(ValueError, match=rf"did you mean {hint}\?"):
            run(source, IO())

    @pytest.mark.parametrize("source", ["[XYZ]", "[PRP]", "[P]", "[S]", "[p 5]"])
    def test_unknown_command_without_unique_match_has_no_hint(
        self, source: str
    ) -> None:
        with pytest.raises(ValueError, match="is not a Modulous command") as error:
            run(source, IO())
        assert "did you mean" not in str(error.value)

    def test_text_outside_a_command_is_refused(self) -> None:
        """``findall`` dropped it, so an unbalanced bracket ran half a program."""
        with pytest.raises(ValueError, match="outside any"):
            run("[PSH INT 1[END]", IO())
        with pytest.raises(ValueError, match="outside any"):
            run("[END] trailing junk", IO())

    def test_whitespace_between_commands_is_still_fine(self) -> None:
        """The refusal must not reject the layout every program uses."""
        run("[PSH INT 1]\n\n  [POP]\t[END]", IO())


class TestStepMachine:
    def test_a_token_less_state_starts_halted(self) -> None:
        from esolangs.interpreters.stack_based.modulous import _Machine

        # `step` has no halted guard of its own -- the caller checks first,
        # which is what the VM's run loop does.
        assert _Machine("", IO()).halted

    def test_snapshot_is_hashable_and_tracks_progress(self) -> None:
        from esolangs.interpreters.stack_based.modulous import _Machine

        state = _Machine("[PSH INT 5][PRT INT][END]", IO())
        before = state.snapshot()
        hash(before)  # must not raise
        state.step()
        assert state.snapshot() != before

    def test_a_read_loop_on_a_cursorless_port_is_not_a_cycle(self) -> None:
        """An input port with no cursor reports position 0 after every read."""
        from esolangs.interpreters.stack_based.modulous import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        class _Cursorless(ScriptedIO):
            def position(self) -> int:
                return 0

        machine = _Machine("[INP STR][POP][RST]", _Cursorless("a\na\n"))
        with pytest.raises(EOFError):
            run_until_halt_or_cycle(machine, limit=100)


class TestBranchingMachine:
    @pytest.mark.parametrize("command", ["PRT", "PRT INT"])
    def test_branching_accepts_valid_output(self, command: str) -> None:
        from esolangs.interpreters.stack_based.modulous import _Machine
        from esolangs.vm import run_until_halt, run_until_halt_or_all_branches_cycle

        code = f"[PSH INT 65][{command}][END]"
        io = ScriptedIO("")
        assert run_until_halt(_Machine(code, io), limit=3)
        assert io.getvalue() == ("65" if command == "PRT INT" else "A")
        assert run_until_halt_or_all_branches_cycle(
            _Machine(code, ScriptedIO("")), limit=4
        )

    @pytest.mark.parametrize(
        ("code", "message"),
        [("[TYPO]", "is not a Modulous command"), ("[PSH INT -1][PRT]", "chr")],
    )
    def test_branching_rejects_invalid_programs_like_execution(
        self, code: str, message: str
    ) -> None:
        from esolangs.interpreters.stack_based.modulous import _Machine
        from esolangs.vm import run_until_halt, run_until_halt_or_all_branches_cycle

        for runner in (run_until_halt, run_until_halt_or_all_branches_cycle):
            with pytest.raises(ValueError, match=message):
                runner(_Machine(code, ScriptedIO("")), limit=10)

    @pytest.mark.parametrize("distance", [1, 100, 101])
    def test_branching_wraps_backward_jumps_like_execution(self, distance: int) -> None:
        from esolangs.interpreters.stack_based.modulous import _Machine
        from esolangs.vm import run_until_halt, run_until_halt_or_all_branches_cycle

        code = f"[JMP B {distance}][END]"
        expected = run_until_halt(_Machine(code, ScriptedIO("")), limit=10)
        assert (
            run_until_halt_or_all_branches_cycle(
                _Machine(code, ScriptedIO("")), limit=10
            )
            == expected
        )
