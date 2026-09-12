r"""Unit tests for the Bitdeque interpreter."""

import io
from contextlib import redirect_stdout

from esolangs.interpreters.io import IO
from esolangs.interpreters.queue_based.bitdeque import run
from tests.interpreters.contract import (
    CycleContract,
    SnapshotContract,
    StateViewContract,
)


def run_and_capture(code: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestBitdeque:
    def test_push_zeros(self) -> None:
        assert run_and_capture("PUSH PUSH PUSH") == "0 0 0"

    def test_invert_then_push(self) -> None:
        assert run_and_capture("INVERT PUSH PUSH") == "1 1"

    def test_pop_restores_register(self) -> None:
        assert run_and_capture("PUSH POP PUSH") == "0"

    def test_invert_parity(self) -> None:
        assert run_and_capture("INVERT INVERT INVERT PUSH") == "1"

    def test_empty_deque_prints_nothing(self) -> None:
        assert run_and_capture("POP") == ""

    def test_goto(self) -> None:
        r"""GOTO with a nonzero register jumps to a numbered instruction."""
        assert run_and_capture("INVERT GOTO 2 PUSH PUSH") == "1 1"

    def test_goto_does_not_jump_on_a_zero_register(self) -> None:
        r"""GOTO is conditional, and nothing else here reaches the false arm."""
        assert run_and_capture("GOTO 2 PUSH PUSH") == "0 0"

    def test_goto_target_is_zero_based(self) -> None:
        r"""GOTO N lands on the Nth command counting from zero."""
        assert run_and_capture("INVERT GOTO 3 PUSH PUSH") == "1"

    def test_goto_without_a_space(self) -> None:
        r"""The space after GOTO is optional, as the token pattern allows."""
        assert run_and_capture("INVERT GOTO12 PUSH PUSH") == ""

    def test_goto_takes_any_run_of_spaces(self) -> None:
        r"""The pattern allows any number of spaces, not just nought or one."""
        assert run_and_capture("INVERT GOTO  3 PUSH PUSH") == "1"

    def test_inject_adds_to_the_front(self) -> None:
        r"""INJECT puts the register at the front, where PUSH appends."""
        assert run_and_capture("INVERT PUSH INVERT INJECT") == "0 1"
        assert run_and_capture("INVERT PUSH PUSH INVERT INJECT") == "0 1 1"

    def test_push_appends_rather_than_prepending(self) -> None:
        r"""PUSH works the back, told apart from INJECT rather than from."""
        assert run_and_capture("INVERT PUSH PUSH INVERT PUSH") == "1 1 0"

    def test_eject_takes_from_the_front(self) -> None:
        r"""EJECT pops the front, where POP takes the back."""
        assert run_and_capture("INVERT PUSH INVERT PUSH EJECT PUSH") == "0 1"
        assert run_and_capture("INVERT PUSH INVERT PUSH POP PUSH") == "1 0"

    def test_taking_from_an_empty_deque_gives_zero(self) -> None:
        r"""POP and EJECT on an empty deque clear the register."""
        assert run_and_capture("INVERT POP PUSH") == "0"
        assert run_and_capture("INVERT EJECT PUSH") == "0"

    def test_invert_is_a_flip_not_a_set(self) -> None:
        r"""Two INVERTs cancel; the register is flipped, not set to one."""
        assert run_and_capture("INVERT INVERT PUSH") == "0"


class TestStepMachine:
    def test_step_tracks_cursor_register_and_deque(self) -> None:
        from esolangs.interpreters.io import IO
        from esolangs.interpreters.queue_based.bitdeque import _Machine

        machine = _Machine("INVERT PUSH", IO())
        assert (machine.ind, machine.reg, machine.deq) == (0, 0, ())
        machine.step()  # INVERT flips the register.
        assert (machine.ind, machine.reg) == (1, 1)
        machine.step()  # PUSH appends the register.
        assert machine.deq == (1,)
        assert machine.halted
        machine.step()  # the post-halt step renders,.
        assert machine.ind == 2

    def test_the_deque_renders_once_however_far_it_is_stepped(self) -> None:
        r"""The post-halt step prints the deque, and only the first one does."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.queue_based.bitdeque import _Machine

        io_obj = ScriptedIO()
        machine = _Machine("PUSH INVERT", io_obj)
        while not machine.halted:
            machine.step()
        assert io_obj.getvalue() == ""  # nothing until the step past.
        machine.step()
        assert io_obj.getvalue() == "0"
        for _ in range(3):
            machine.step()
        assert io_obj.getvalue() == "0"


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.queue_based.bitdeque import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract, CycleContract, StateViewContract):
    r"""The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "PUSH"
    halting_program = "INVERT PUSH"
    looping_program = "INVERT GOTO 1"
    # `rendered` guards the.
    # step past the halt; it is.
    # what the run moves.
    state_views = ("rendered", "ip", "memory")
    viewing_program = "INVERT PUSH"
    # `rendered` latches on the.
    # stops at the halt, so no.
    constant_views = frozenset({"rendered"})
