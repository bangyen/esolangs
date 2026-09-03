"""Unit tests for the ROTfuck interpreter.

The rotation makes a raw program's characters drift along ``+-><,.[]``, so
the interesting property is that a position ``i`` whose source character is
the ``i``-fold inverse rotation of a command executes exactly that command
when the pointer reaches it.  ``build`` encodes a sequence of *effective*
commands that way, letting the tests read like plain brainfuck while pinning
the rotation semantics.

Brackets match dynamically: when a ``[`` or ``]`` fires it rotates the
program first and then seeks for its partner in the rotated program, so
partners need not (and usually do not) exist at the same positions in the
source.  A bracket that fires with no partner in the rotated program is a
runtime error.
"""

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
    """Encode ``commands`` as a ROTfuck program.

    The character at position ``i`` is the ``i``-fold inverse rotation of
    the command it should execute when the pointer reaches it.
    """
    return "".join(_CHAIN[(_CHAIN.index(c) - i) % 8] for i, c in enumerate(commands))


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    with contextlib.suppress(EOFError):
        run(code, io)
    return io.getvalue()


class TestRotation:
    def test_program_rotates_after_every_command(self) -> None:
        # two raw ','s: the first reads 'A', then the program rotates so the
        # second ',' is now '.', which prints the cell.
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
        """< at the left edge does nothing (matches the Brainfuck semantics)."""
        assert run_program(build("<<.")) == "\x00"

    def test_right_moves_one_cell_each_time(self) -> None:
        """``>`` advances the pointer rather than setting it.

        A pointer that jumped to a fixed cell still prints the same values
        while every write lands where it is read -- so the test has to mark
        one cell and then print a *different* one.  Here cell 1 is set to
        2 and two further moves put the pointer on cell 3, which is empty:
        a pointer that returned to 1 would print the mark instead.
        """
        assert run_program(build(">++>>.")) == "\x00"
        assert run_program(build(">>>+.")) == "\x01"

    def test_minus_decrements_the_current_cell(self) -> None:
        """``-`` is its own command, distinct from the other seven.

        The wrap test reaches 0 by adding 256 times, so ``-`` was only ever
        seen through a cell that was already going to be zero.  One
        decrement from a fresh cell gives 255, which nothing else does.
        """
        assert run_program(build("-.")) == "\xff"
        assert run_program(build("--.")) == "\xfe"

    def test_comments_ignored(self) -> None:
        # trailing comments are skipped by the pointer and never rotate
        assert run_program(build("+.") + "abc") == "\x01"
        assert run_program("xyz") == ""

    def test_comments_do_not_rotate_the_program(self) -> None:
        """A comment is passed over, not executed, so it does not rotate.

        The spec rotates "every time an instruction is executed", and a
        comment character is not an instruction.  Only a *mid-program*
        comment can show this: a trailing one cannot affect output that
        has already been printed, which is why the case above passes
        either way.  Here the comments sit between the ``+`` and the
        ``.``, so a comment that rotated would advance the ``.`` along
        the cycle and print the wrong byte (or turn it into a bracket).
        """
        expected = run_program(build("+."))
        assert expected == "\x01"
        for comment in ("x", "xxx", "   ", "\n", "hello world"):
            program = build("+.")
            spliced = program[0] + comment + program[1]
            assert run_program(spliced) == expected, f"comment {comment!r} rotated"


class TestIO:
    def test_input_echo(self) -> None:
        assert run_program(build(",>,<.>."), "A\nB") == "AB"

    def test_input_running_out_raises_eof(self) -> None:
        io = ScriptedIO("")
        with pytest.raises(EOFError):
            run(build(","), io)


class TestBrackets:
    def test_wiki_cat_example_runs(self) -> None:
        """The wiki's `,[` cat no longer errors: the ] finds a [ dynamically."""
        assert run_program(",[", "x") == ""

    def test_backward_jump_fires_in_rotated_program(self) -> None:
        """A ] fires, rotates, and jumps back to a [ found in the result.

        In ``+<.]>`` the fired ``]`` first jumps back to the ``[`` of ``[+``
        and later to the ``[`` of ``[-<.``: neither partner exists in the
        source, so a static match (as a raw brainfuck would do) has no
        target at all.
        """
        assert run_program("+<.]>", "x") == ""

    def test_forward_skip_over_nested_bracket(self) -> None:
        """A skipped ``[`` seeks its partner past a nested ``[``."""
        assert run_program("[[.].]") == ""

    def test_forward_skip_passes_a_nested_closer(self) -> None:
        """The scan steps over a ``]`` that closes the *inner* pair.

        ``[[.].]`` above enters at depth 1 and meets its partner first; here
        the skipped ``[`` opens over a nested pair, so the first ``]`` the
        scan reaches is at depth 2 and must not end it.  The program prints
        after the skipped body, which a scan that stopped early would miss.
        """
        assert run_program(build(".[[+-")) == "\x00"

    def test_backward_jump_over_nested_bracket(self) -> None:
        """A fired ``]`` jumps back across a nested ``]`` in the rotation."""
        assert run_program("<+..>[]") == "\x01"

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
        """The seek counts nesting even on the way to failing.

        Both seeks are usually watched through a jump that *succeeds*,
        where a miscounted opener still tends to land on some closer.
        These programs have no partner at all, so the count is the only
        thing that decides -- a seek that ignores a nested opener, or that
        pins its depth at one, finds a false partner and the program runs
        on instead of halting.
        """
        with pytest.raises(HaltError):
            run_program(build("[[+"))
        with pytest.raises(HaltError):
            run_program(build("+[<.]"))

    def test_the_partnerless_bracket_message_names_which_one_fired(self) -> None:
        """Each direction reports its own bracket, and the text is pinned.

        The cases above only check that *something* halted, so the two
        messages were free to be rewritten or swapped -- and a bare
        ``HaltError`` with no message at all reads the same to
        ``pytest.raises``.  Asserting the string separates the forward seek
        from the backward one.
        """
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
