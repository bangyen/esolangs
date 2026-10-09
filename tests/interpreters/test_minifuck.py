"""Unit tests for the Minifuck interpreter."""

import pytest

from esolangs.interpreters.tape_based.minifuck import run
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    InputCursorContract,
    SnapshotContract,
    StateViewContract,
)
from tests.interpreters.runner import run_lines

run_and_capture = run_lines(run)


class TestMinifuck:
    def test_cat_program(self) -> None:
        """The canonical cat program echoes its input."""
        assert run_and_capture("<[<.[<.", inputs=["B"]) == "B"

    def test_comment_characters_ignored(self) -> None:
        """Non-command characters are ignored."""
        assert run_and_capture("abc", inputs=["A"]) == ""

    def test_tape_grows_past_the_initial_eight_cells(self) -> None:
        """The tape extends once the pointer nears its end, and . reads 8 cells."""
        assert run_and_capture("[[[[[[[.") == "\x7f"

    def test_an_unlisted_character_is_not_a_command(self) -> None:
        """A character that is neither ``<`` nor ``.`` nor ``[`` does nothing."""
        assert run_and_capture("X.") == "@"
        assert run_and_capture("X") == ""

    def test_the_skip_flips_the_cell_after_the_pointer(self) -> None:
        """``[`` collapsing to 0 flips ``ptr + 1``, not ``ptr - 1``."""
        assert run_and_capture("[[[[[[[<<<[<.") == "{"  # 0b01111011

    def test_the_skip_passes_exactly_one_instruction(self) -> None:
        """``[`` that flips a cell to 0 skips one instruction, not two."""
        assert run_and_capture("[<[<<.") == "`"  # 0b01100000

    def test_a_read_keeps_the_cell_past_the_print_window(self) -> None:
        """A read replaces cells 0-7 and leaves cell 8 alone, shown in output."""
        witness = "[" * 8 + "<<." * 7 + "." * 6 + "[."
        assert run_and_capture(witness, inputs=["A"]) == "~|xp`@aqy}\x7f~"


class TestStepMachine:
    def test_step_tracks_tape_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        machine = _Machine(".", ScriptedIO())
        assert (machine.ind, machine.ptr) == (0, 0)
        machine.step()  # . advances, flips the second cell, prints the byte
        assert machine.io.getvalue() == "@"
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 1

    def test_tape_state_when_the_pointer_runs_deep(self) -> None:
        """The grown tape's exact contents, not just the byte it prints."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        machine = _Machine("[[[[[[[", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.ptr == 7
        assert machine.tape == [0, 1, 1, 1, 1, 1, 1, 1, 0]

    def test_the_tape_starts_eight_cells_wide(self) -> None:
        """The tape starts eight cells wide, which no output can reveal."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        assert _Machine("", ScriptedIO()).tape == [0] * 8

    def test_a_read_keeps_the_tape_past_the_print_window(self) -> None:
        """Reading input replaces cells 0-7 and keeps everything after them."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        machine = _Machine(".<<[<<<.[<<.<<<..[<[.[.[..", ScriptedIO("ABCDEFGH"))
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == "@`p0\x10"
        assert machine.tape == [0, 1, 0, 0, 0, 0, 0, 1, 0]


class TestVMViews:
    """That ``ip``/``memory``/``stack`` read what they name."""

    def test_the_vm_views_read_the_state_they_name(self) -> None:
        machine = _drive("[.<")
        assert machine.ip == machine.ind == 3
        assert machine.ptr == 1
        assert machine.memory == machine.tape == [0, 1, 1, 0, 0, 0, 0, 0]
        assert not hasattr(machine, "stack")

    def test_the_tape_views_hand_back_copies(self) -> None:
        """A caller cannot write through ``tape`` or ``memory``."""
        machine = _drive("[.<")
        assert machine.tape is not machine.tape
        assert machine.memory is not machine.memory
        machine.tape[0] = 1
        machine.memory[1] = 0
        assert machine.tape == [0, 1, 1, 0, 0, 0, 0, 0]


@pytest.mark.parametrize(
    ("ins", "tape", "ptr", "expected"),
    [
        # `<` moves and does nothing else, and stops at the origin.
        ("<", 0, 3, (0, 8, 2, False, None, False)),
        ("<", 0, 0, (0, 8, 0, False, None, False)),
        # A comment leaves every scalar alone.
        ("x", 0b10, 1, (0b10, 8, 1, False, None, False)),
        # `.` prints its window, or reads when the flip empties it.  The
        # printing arm's `reads` is False, which nothing driving the
        # interpreter can see -- `_advance` tests `char is not None` first --
        # so only this table pins it.
        (".", 0, 0, (0b10, 8, 1, False, "@", False)),
        (".", 0b10, 0, (0, 8, 1, False, None, True)),
        # ... and the window is masked, so a lone cell 8 reads as empty.
        (".", 0, 7, (1 << 8, 9, 8, False, None, True)),
        # `[` flips and stays, or flips to zero and collapses.
        ("[", 0, 0, (0b10, 8, 1, False, None, False)),
        ("[", 0b10, 0, (0b100, 8, 1, True, None, False)),
        # The tape grows one cell before the pointer needs it.
        ("[", 0, 7, (1 << 8, 9, 8, False, None, False)),
    ],
)
def test_step_is_the_language_as_plain_scalars(
    ins: str,
    tape: int,
    ptr: int,
    expected: tuple[int, int, int, bool, str | None, bool],
) -> None:
    """``_step`` is the definition the boolean emitter's laws are pinned to."""
    from esolangs.interpreters.tape_based.minifuck import _step

    assert _step(ins, tape, 8, ptr) == expected


def _machine(code: object, stdin: str = "") -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.minifuck import _Machine

    return _Machine(code, ScriptedIO(stdin))


def _drive(code: str, stdin: str = "") -> object:
    """Run a machine to its halt and hand it back for inspection."""
    machine = _machine(code, stdin)
    while not machine.halted:
        machine.step()
    return machine


class TestContract(
    EmptyProgramContract,
    SnapshotContract,
    CycleContract,
    InputCursorContract,
    StateViewContract,
):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_and_capture)
    machine = staticmethod(_machine)
    stepping_program = "."
    halting_program = "."
    no_cycle_reason = "Minifuck advances its code cursor on every step."

    reader = staticmethod(_machine)
    reading_program = ".<."
    reading_stdin = "a"
    steps_before_read = 2
    steps_to_read = 1
    position_after_read = 1

    state_views = ("tape", "ptr", "ind", "ip", "memory", "halted")
    viewing_program = "[.<"


@pytest.mark.parametrize("code", ["<", "[[<[[", "[[[[[[[<<<[<.", ".", "comment"])
def test_forward_cursor_precludes_cycles(code: str) -> None:
    machine = _machine(code)
    steps = 0
    while not machine.halted:
        before = machine.ind
        machine.step()
        assert machine.ind > before
        steps += 1
        assert steps <= len(code)
