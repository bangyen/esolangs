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


class TestBrackets:
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
