"""Unit tests for the Unsquare interpreter."""

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.unsquare import run
from tests.interpreters.contract import (
    CycleContract,
    InputCursorContract,
    StateViewContract,
)


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class TestStepMachine:
    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.stack_based.unsquare import _Machine

        machine = _Machine("", ScriptedIO())
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.stack == ()


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.unsquare import _Machine

    return _Machine(code, ScriptedIO())


def _reader(code: object, stdin: str) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.unsquare import _Machine

    return _Machine(code, ScriptedIO(stdin))


class TestContract(CycleContract, InputCursorContract, StateViewContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    reader = staticmethod(_reader)
    reading_program = "i"
    reading_stdin = "hi"
    halting_program = "Io"
    looping_program = "IIAx><"
    # `I` pushes and `o` prints, so the cursor and the data stack both move
    # while the jump stack stays empty -- which is the point: they are
    # separate slots, not one field read under four names.
    state_views = ("ind", "acc", "stack", "jumps", "ip", "memory")
    # The loop test's own program: it moves the accumulator, the jump
    # stack, and the data stack, where "Io" moved only the last.
    viewing_program = "++>Po-<"


def test_loading_a_stack_detaches_it_and_preserves_other_state() -> None:
    from esolangs.interpreters.stack_based.unsquare import _Machine

    machine = _Machine("+o", ScriptedIO())
    machine.step()
    values = [65, 66]
    machine.load(values)
    values[1] = 67
    assert machine.stack == (65, 66)
    assert machine.acc == 2
    machine.step()
    assert machine.io.getvalue() == "B"
