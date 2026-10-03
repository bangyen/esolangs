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
from tests.interpreters.runner import run_program


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


class TestVMViews:
    """Tape views cannot mutate the machine."""

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
    """``_step`` is the definition the boolean emitter's laws are pinned to.

    Everything else here drives the interpreter, which packs these six
    scalars into a state and an effect and drops what it does not need.
    That makes the tuple itself untested from this file: a mutation setting
    ``reads`` on the *printing* arm survives the whole suite, because
    ``_advance`` never looks at ``reads`` once ``char`` is set.  It is
    caught only in ``tests/tools/test_boolean_minifuck_sim*.py``, a suite
    away from the definition it protects.
    """
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
