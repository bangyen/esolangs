"""Unit tests for the ROTfuck interpreter."""

from functools import partial

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.rotfuck import run
from tests.interpreters import runner
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    SnapshotContract,
)

_CHAIN = "+-><,.[]"


def build(commands: str) -> str:
    """Encode ``commands`` as a ROTfuck program."""
    return "".join(_CHAIN[(_CHAIN.index(c) - i) % 8] for i, c in enumerate(commands))


run_program = partial(runner.run_program, run)


class TestRotation:
    def test_program_rotates_after_every_command(self) -> None:
        # two raw ','s: the first reads 'A', then the program rotates so the
        # second ',' is now '.', which prints the cell.
        assert run_program(",,", "A") == "A"


class TestTape:
    def test_left_of_cell_zero_is_a_fresh_zero_cell(self) -> None:
        """< at the left edge grows the tape onto a new zero cell."""
        assert run_program(build("+<.")) == "\x00"
        assert run_program(build("+<<<.")) == "\x00"

    def test_left_of_zero_and_back_keeps_both_cells(self) -> None:
        """The grown cell and the start cell are distinct and both kept."""
        assert run_program(build("+<++>.<.")) == "\x01\x02"
        assert run_program(build("+<<<<>>>>.")) == "\x01"

    def test_the_step_machine_grows_left_as_run_does(self) -> None:
        from esolangs.interpreters.tape_based.rotfuck import _Machine

        machine = _Machine(build("+<<++>"), ScriptedIO())
        while not machine.halted:
            machine.step()
        assert (machine.tape, machine.ptr) == ((2, 0, 1), 1)

    def test_comments_do_not_rotate_the_program(self) -> None:
        """A comment is passed over, not executed, so it does not rotate."""
        expected = run_program(build("+."))
        assert expected == "\x01"
        for comment in ("x", "xxx", "   ", "\n", "hello world"):
            program = build("+.")
            spliced = program[0] + comment + program[1]
            assert run_program(spliced) == expected, f"comment {comment!r} rotated"


class TestIO:
    def test_an_input_character_above_255_is_taken_modulo_256(self) -> None:
        """``,`` writes a cell, so it reduces as ``+`` and ``-`` do."""
        assert run_program(build(",."), "Ā") == "\x00"
        assert run_program(build(",."), "ā") == "\x01"
        assert run_program(build(",+."), "Ā") == "\x01"

    def test_input_running_out_raises_eof(self) -> None:
        io = ScriptedIO("")
        with pytest.raises(EOFError):
            run(build(","), io)


class TestBrackets:
    def test_wiki_cat_example_runs(self) -> None:
        """The wiki's `,[` cat no longer errors: the ] finds a [ dynamically."""
        assert run_program(",[", "x") == ""

    def test_backward_jump_fires_in_rotated_program(self) -> None:
        """A ] fires, rotates, and jumps back to a [ found in the result."""
        assert run_program("+<.]>", "x") == ""

    def test_forward_skip_over_nested_bracket(self) -> None:
        """A skipped ``[`` seeks its partner past a nested ``[``."""
        assert run_program("[[.].]") == ""

    def test_forward_skip_passes_a_nested_closer(self) -> None:
        """The scan steps over a ``]`` that closes the *inner* pair."""
        assert run_program(build(".[[+-")) == "\x00"

    def test_backward_jump_over_nested_bracket(self) -> None:
        """A fired ``]`` jumps back across a nested ``]`` in the rotation."""
        from esolangs.interpreters.tape_based.rotfuck import _Machine

        # Index 4 fires as ``]`` and, rotated, finds its ``[`` at index 1
        # past the ``]`` at index 3; the replayed ``+``/``>`` leave (2, 1).
        machine = _Machine("+--><+", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert (machine.io.getvalue(), machine.tape) == ("\x01", (2, 1))

    def test_unmatched_bracket_halts_when_executed(self) -> None:
        """A fired bracket with no partner in the rotated program errors."""
        with pytest.raises(HaltError):
            run_program("[.]")
        with pytest.raises(HaltError):
            run_program("+[]")
        with pytest.raises(HaltError):
            run_program(build("+]"))
        with pytest.raises(HaltError):
            run_program("[")

    def test_unmatched_bracket_that_never_runs_is_fine(self) -> None:
        """Unbalanced sources are legal; only execution matters."""
        assert run_program(build(".")) == "\x00"

    def test_a_nested_opener_is_counted_when_no_partner_exists(self) -> None:
        """The seek counts nesting even on the way to failing."""
        with pytest.raises(HaltError):
            run_program(build("[[+"))
        with pytest.raises(HaltError):
            run_program(build("+>+[<.]"))

    def test_the_partnerless_bracket_message_names_which_one_fired(self) -> None:
        """Each direction reports its own bracket, and the text is pinned."""
        with pytest.raises(HaltError) as caught:
            run_program(build("["))
        assert str(caught.value) == "an executed '[' has no bracket partner"

        with pytest.raises(HaltError) as caught:
            run_program(build("+]"))
        assert str(caught.value) == "an executed ']' has no bracket partner"


class TestStepMachine:
    def test_step_tracks_tape_cursor_and_rotation(self) -> None:
        from esolangs.interpreters.tape_based.rotfuck import _Machine

        machine = _Machine(build("+."), ScriptedIO())
        assert (machine.ind, machine.ptr, list(machine.tape)) == (0, 0, [0])
        machine.step()  # + increments the cell and rotates the program
        assert list(machine.tape) == [1]
        assert machine.prog.rotation() == 1
        machine.step()  # . prints the cell and rotates again
        assert machine.io.getvalue() == "\x01"
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 2

    def test_pure_transition_moves_left_and_checks_backward_partners(self) -> None:
        from esolangs.interpreters.tape_based.rotfuck import _advance

        chars = tuple("<[]")
        assert _advance(((0, 1), 1, 0, 0), chars) == ((0, 1), 0, 1, 1)
        assert _advance(((7,), 0, 0, 0), tuple("<")) == ((0, 7), 0, 1, 1)
        assert _advance(((1,), 0, 1, 0), tuple(".]")) == ((1,), 0, 1, 1)

        with pytest.raises(HaltError):
            _advance(((1,), 0, 0, 0), tuple("]"))
        with pytest.raises(HaltError, match="'\\['"):
            _advance(((0,), 0, 0, 0), tuple("["))


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.rotfuck import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, SnapshotContract, CycleContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
    machine = staticmethod(_machine)
    stepping_program = "."
    halting_program = "."
    no_cycle_reason = "ROTfuck snapshots retain the increasing rotation count."


@pytest.mark.parametrize("code", [build("+-><,.[]"), "+<.]>", "[[]", "comment"])
def test_rotation_and_cursor_preclude_snapshot_cycles(code: str) -> None:
    from esolangs.interpreters.tape_based.rotfuck import _Machine

    machine = _Machine(code, ScriptedIO("x\n" * 100))
    for _ in range(100):
        if machine.halted:
            break
        before = machine.snapshot()
        rank = (machine.prog.rotation(), machine.ind)
        try:
            machine.step()
        except HaltError:
            break
        assert (machine.prog.rotation(), machine.ind) > rank
        assert machine.snapshot() != before
