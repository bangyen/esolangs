"""Unit tests for the Modulous interpreter."""


import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.stack_based.modulous import run
from tests.interpreters.runner import run_program


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


class TestModulous:
    def test_push_print_int(self) -> None:
        assert run_and_capture("[PSH INT 5][PRT INT][END]") == "5"

    def test_push_print_string(self) -> None:
        assert run_and_capture('[PSH STR "A"][PRT][END]') == "A"

    def test_push_string_then_pop(self) -> None:
        assert run_and_capture('[PSH STR "AB"][PRT][PRT][END]') == "AB"

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
