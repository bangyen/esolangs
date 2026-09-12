r"""Unit tests for the ROTfuck interpreter."""

import contextlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.rotfuck import run
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    SnapshotContract,
)

_CHAIN = "+-><,.[]"


def build(commands: str) -> str:
    r"""Encode ``commands`` as a ROTfuck program."""
    return "".join(_CHAIN[(_CHAIN.index(c) - i) % 8] for i, c in enumerate(commands))


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    with contextlib.suppress(EOFError):
        run(code, io)
    return io.getvalue()


class TestRotation:
    def test_program_rotates_after_every_command(self) -> None:
        # two raw ','s: the first reads.
        # second ',' is now '.', which.
        assert run_program(",,", "A") == "A"

    def test_single_command(self) -> None:
        assert run_program(build(".")) == "\x00"

    def test_build_encoding(self) -> None:
        assert run_program(build("+" * 65 + ".")) == "A"


class TestTape:
    def test_cell_wraps(self) -> None:
        assert run_program(build("+" * 256 + ".")) == "\x00"

    def test_movement(self) -> None:
        assert run_program(build("++>++<.>.>")) == "\x02\x02"

    def test_left_clamped(self) -> None:
        r"""< at the left edge does nothing (matches the Brainfuck semantics)."""
        assert run_program(build("<<.")) == "\x00"

    def test_right_moves_one_cell_each_time(self) -> None:
        r"""``>`` advances the pointer rather than setting it."""
        assert run_program(build(">++>>.")) == "\x00"
        assert run_program(build(">>>+.")) == "\x01"

    def test_minus_decrements_the_current_cell(self) -> None:
        r"""``-`` is its own command, distinct from the other seven."""
        assert run_program(build("-.")) == "\xff"
        assert run_program(build("--.")) == "\xfe"

    def test_comments_ignored(self) -> None:
        # trailing comments are skipped.
        assert run_program(build("+.") + "abc") == "\x01"
        assert run_program("xyz") == ""

    def test_comments_do_not_rotate_the_program(self) -> None:
        r"""A comment is passed over, not executed, so it does not rotate."""
        expected = run_program(build("+."))
        assert expected == "\x01"
        for comment in ("x", "xxx", "   ", "\n", "hello world"):
            program = build("+.")
            spliced = program[0] + comment + program[1]
            assert run_program(spliced) == expected, f"comment {comment!r} rotated"


class TestIO:
    def test_input_echo(self) -> None:
        assert run_program(build(",>,<.>."), "A\nB") == "AB"

    def test_an_input_character_above_255_is_taken_modulo_256(self) -> None:
        r"""``,`` writes a cell, so it reduces as ``+`` and ``-`` do."""
        assert run_program(build(",."), "Ā") == "\x00"
        assert run_program(build(",."), "ā") == "\x01"
        assert run_program(build(",+."), "Ā") == "\x01"

    def test_input_running_out_raises_eof(self) -> None:
        io = ScriptedIO("")
        with pytest.raises(EOFError):
            run(build(","), io)


class TestBrackets:
    def test_wiki_cat_example_runs(self) -> None:
        r"""The wiki's `,[` cat no longer errors: the ] finds a [ dynamically."""
        assert run_program(",[", "x") == ""

    def test_backward_jump_fires_in_rotated_program(self) -> None:
        r"""A ] fires, rotates, and jumps back to a [ found in the result."""
        assert run_program("+<.]>", "x") == ""

    def test_forward_skip_over_nested_bracket(self) -> None:
        r"""A skipped ``[`` seeks its partner past a nested ``[``."""
        assert run_program("[[.].]") == ""

    def test_forward_skip_passes_a_nested_closer(self) -> None:
        r"""The scan steps over a ``]`` that closes the *inner* pair."""
        assert run_program(build(".[[+-")) == "\x00"

    def test_backward_jump_over_nested_bracket(self) -> None:
        r"""A fired ``]`` jumps back across a nested ``]`` in the rotation."""
        assert run_program("<+..>[]") == "\x01"

    def test_unmatched_bracket_halts_when_executed(self) -> None:
        r"""A fired bracket with no partner in the rotated program errors."""
        with pytest.raises(HaltError):
            run_program("[.]")
        with pytest.raises(HaltError):
            run_program("+[]")
        with pytest.raises(HaltError):
            run_program(build("+]"))
        with pytest.raises(HaltError):
            run_program("[")

    def test_unmatched_bracket_that_never_runs_is_fine(self) -> None:
        r"""Unbalanced sources are legal; only execution matters."""
        assert run_program(build(".")) == "\x00"

    def test_a_nested_opener_is_counted_when_no_partner_exists(self) -> None:
        r"""The seek counts nesting even on the way to failing."""
        with pytest.raises(HaltError):
            run_program(build("[[+"))
        with pytest.raises(HaltError):
            run_program(build("+[<.]"))

    def test_the_partnerless_bracket_message_names_which_one_fired(self) -> None:
        r"""Each direction reports its own bracket, and the text is pinned."""
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
        machine.step()  # + increments the cell and.
        assert list(machine.tape) == [1]
        assert machine.prog.rotation() == 1
        machine.step()  # .
        assert machine.io.getvalue() == "\x01"
        assert machine.halted
        machine.step()  # stepping a halted machine is.
        assert machine.ind == 2


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.rotfuck import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, SnapshotContract, CycleContract):
    r"""The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
    machine = staticmethod(_machine)
    stepping_program = "."
    halting_program = "."
