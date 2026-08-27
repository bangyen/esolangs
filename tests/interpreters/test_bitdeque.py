"""Unit tests for the Bitdeque interpreter."""

import io
from contextlib import redirect_stdout

from esolangs.interpreters.io import IO
from esolangs.interpreters.queue_based.bitdeque import run


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
        """GOTO with a nonzero register jumps to a numbered instruction."""
        assert run_and_capture("INVERT GOTO 2 PUSH PUSH") == "1 1"

    def test_goto_target_is_zero_based(self) -> None:
        """GOTO N lands on the Nth command counting from zero.

        ``test_goto`` jumps to 2, and the two commands after the GOTO are
        both PUSH -- so landing on either printed the same thing.  Jumping
        to 3 skips the first of them and prints one value instead of two.
        """
        assert run_and_capture("INVERT GOTO 3 PUSH PUSH") == "1"

    def test_goto_without_a_space(self) -> None:
        """The space after GOTO is optional, as the token pattern allows.

        With a space the target is read from ``"GOTO 3"[4:]`` -- ``" 3"`` --
        which int() parses the same as ``"3"``, so dropping one more
        character made no difference to any spaced program.  Written tight,
        the two disagree: one reads 12 and the other 2.
        """
        assert run_and_capture("INVERT GOTO12 PUSH PUSH") == ""

    def test_inject_adds_to_the_front(self) -> None:
        """INJECT puts the register at the front, where PUSH appends.

        Nothing in the suite used INJECT at all: the token could be spelled
        anything and every test still passed.
        """
        assert run_and_capture("INVERT PUSH INVERT INJECT") == "0 1"
        assert run_and_capture("INVERT PUSH PUSH INVERT INJECT") == "0 1 1"

    def test_eject_takes_from_the_front(self) -> None:
        """EJECT pops the front, where POP takes the back.

        EJECT went unused too, so the two ends were never told apart: the
        same program run through POP leaves the other value behind.
        """
        assert run_and_capture("INVERT PUSH INVERT PUSH EJECT PUSH") == "0 1"
        assert run_and_capture("INVERT PUSH INVERT PUSH POP PUSH") == "1 0"

    def test_taking_from_an_empty_deque_gives_zero(self) -> None:
        """POP and EJECT on an empty deque clear the register.

        ``test_pop_restores_register`` pops a 0 that was pushed, so the
        register was already 0 and the empty case could have returned
        anything.  Inverting first makes the difference visible.
        """
        assert run_and_capture("INVERT POP PUSH") == "0"
        assert run_and_capture("INVERT EJECT PUSH") == "0"

    def test_invert_is_a_flip_not_a_set(self) -> None:
        """Two INVERTs cancel; the register is flipped, not set to one."""
        assert run_and_capture("INVERT INVERT PUSH") == "0"


class TestStepMachine:
    def test_step_tracks_cursor_register_and_deque(self) -> None:
        from esolangs.interpreters.io import IO
        from esolangs.interpreters.queue_based.bitdeque import _Machine

        machine = _Machine("INVERT PUSH", IO())
        assert (machine.ind, machine.reg, machine.deq) == (0, 0, [])
        machine.step()  # INVERT flips the register
        assert (machine.ind, machine.reg) == (1, 1)
        machine.step()  # PUSH appends the register
        assert machine.deq == [1]
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 2

    def test_snapshot_is_hashable(self) -> None:
        from esolangs.interpreters.io import IO
        from esolangs.interpreters.queue_based.bitdeque import _Machine

        assert hash(_Machine("PUSH", IO()).snapshot()) is not None

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.io import IO
        from esolangs.interpreters.queue_based.bitdeque import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("INVERT PUSH", IO())) is True

    def test_goto_loop_is_detected_as_a_cycle(self) -> None:
        """GOTO 1 with a nonzero register re-enters itself forever."""
        from esolangs.interpreters.io import IO
        from esolangs.interpreters.queue_based.bitdeque import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("INVERT GOTO 1", IO())) is False
