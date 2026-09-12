r"""Unit tests for the Minifuck interpreter."""

import pytest

from esolangs.interpreters.tape_based.minifuck import run
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    InputCursorContract,
    SnapshotContract,
    StateViewContract,
)
from tests.interpreters.runner import run_program


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


class TestMinifuck:
    def test_cat_program(self) -> None:
        r"""The canonical cat program echoes its input."""
        assert run_and_capture("<[<.[<.", inputs=["A"]) == "A"
        assert run_and_capture("<[<.[<.", inputs=["B"]) == "B"

    def test_comment_characters_ignored(self) -> None:
        r"""Non-command characters are ignored."""
        assert run_and_capture("abc", inputs=["A"]) == ""

    def test_tape_grows_past_the_initial_eight_cells(self) -> None:
        r"""The tape extends once the pointer nears its end, and ."""
        assert run_and_capture("[[[[[[[.") == "\x7f"

    def test_an_unlisted_character_is_not_a_command(self) -> None:
        r"""A character that is neither ``<`` nor ``.`` nor ``[`` does nothing."""
        assert run_and_capture("X.") == "@"
        assert run_and_capture("X") == ""

    def test_the_skip_flips_the_cell_after_the_pointer(self) -> None:
        r"""``[`` collapsing to 0 flips ``ptr + 1``, not ``ptr - 1``."""
        assert run_and_capture("[[[[[[[<<<[<.") == "{"  # 0b01111011.

    def test_the_skip_passes_exactly_one_instruction(self) -> None:
        r"""``[`` that flips a cell to 0 skips one instruction, not two."""
        assert run_and_capture("[<[<<.") == "`"  # 0b01100000.

    def test_a_read_keeps_the_cell_past_the_print_window(self) -> None:
        r"""A read replaces cells 0-7 and leaves cell 8 alone, shown in output."""
        witness = "[" * 8 + "<<." * 7 + "." * 6 + "[."
        assert run_and_capture(witness, inputs=["A"]) == "~|xp`@aqy}\x7f~"


class TestStepMachine:
    def test_step_tracks_tape_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        machine = _Machine(".", ScriptedIO())
        assert (machine.ind, machine.ptr) == (0, 0)
        machine.step()  # .
        assert machine.io.getvalue() == "@"
        assert machine.halted
        machine.step()  # stepping a halted machine is.
        assert machine.ind == 1

    def test_tape_state_when_the_pointer_runs_deep(self) -> None:
        r"""The grown tape's exact contents, not just the byte it prints."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        machine = _Machine("[[[[[[[", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.ptr == 7
        assert machine.tape == [0, 1, 1, 1, 1, 1, 1, 1, 0]

    def test_the_tape_starts_eight_cells_wide(self) -> None:
        r"""The tape starts eight cells wide, which no output can reveal."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        assert _Machine("", ScriptedIO()).tape == [0] * 8

    def test_a_read_keeps_the_tape_past_the_print_window(self) -> None:
        r"""Reading input replaces cells 0-7 and keeps everything after them."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        machine = _Machine(".<<[<<<.[<<.<<<..[<[.[.[..", ScriptedIO("ABCDEFGH"))
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == "@`p0\x10"
        assert machine.tape == [0, 1, 0, 0, 0, 0, 0, 1, 0]


class TestVMViews:
    r"""That ``ip``/``memory``/``stack`` read what they name."""

    def test_the_vm_views_read_the_state_they_name(self) -> None:
        machine = _drive("[.<")
        assert machine.ip == machine.ind == 3
        assert machine.ptr == 1
        assert machine.memory == machine.tape == [0, 1, 1, 0, 0, 0, 0, 0]
        assert machine.stack == []

    def test_the_tape_views_hand_back_copies(self) -> None:
        r"""A caller cannot write through ``tape`` or ``memory``."""
        machine = _drive("[.<")
        assert machine.tape is not machine.tape
        assert machine.memory is not machine.memory
        machine.tape[0] = 1
        machine.memory[1] = 0
        assert machine.tape == [0, 1, 1, 0, 0, 0, 0, 0]


@pytest.mark.parametrize(
    ("ins", "tape", "ptr", "expected"),
    [
        # `<` moves and does nothing.
        ("<", 0, 3, (0, 8, 2, False, None, False)),
        ("<", 0, 0, (0, 8, 0, False, None, False)),
        # A comment leaves every scalar.
        ("x", 0b10, 1, (0b10, 8, 1, False, None, False)),
        # `.` prints its window, or.
        # printing arm's `reads` is.
        # interpreter can see --.
        # so only this table pins it.
        (".", 0, 0, (0b10, 8, 1, False, "@", False)),
        (".", 0b10, 0, (0, 8, 1, False, None, True)),
        # .
        (".", 0, 7, (1 << 8, 9, 8, False, None, True)),
        # `[` flips and stays, or flips.
        ("[", 0, 0, (0b10, 8, 1, False, None, False)),
        ("[", 0b10, 0, (0b100, 8, 1, True, None, False)),
        # The tape grows one cell.
        ("[", 0, 7, (1 << 8, 9, 8, False, None, False)),
    ],
)
def test_step_is_the_language_as_plain_scalars(
    ins: str,
    tape: int,
    ptr: int,
    expected: tuple[int, int, int, bool, str | None, bool],
) -> None:
    r"""``_step`` is the definition the boolean emitter's laws are pinned."""
    from esolangs.interpreters.tape_based.minifuck import _step

    assert _step(ins, tape, 8, ptr) == expected


def _machine(code: object, stdin: str = "") -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.minifuck import _Machine

    return _Machine(code, ScriptedIO(stdin))


def _drive(code: str, stdin: str = "") -> object:
    r"""Run a machine to its halt and hand it back for inspection."""
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
    r"""The shared empty-program shape, with this language's data."""

    run = staticmethod(run_and_capture)
    machine = staticmethod(_machine)
    stepping_program = "."
    halting_program = "."

    reader = staticmethod(_machine)
    reading_program = ".<."
    reading_stdin = "a"
    steps_before_read = 2
    steps_to_read = 1
    position_after_read = 1

    state_views = ("tape", "ptr", "ind", "ip", "memory", "stack", "halted")
    viewing_program = "[.<"
    constant_views = frozenset({"stack"})
