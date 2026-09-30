import io
from contextlib import redirect_stdout

import pytest

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
        assert run_and_capture("INVERT GOTO 2 PUSH PUSH") == "1 1"

    def test_goto_does_not_jump_on_a_zero_register(self) -> None:
        """GOTO is conditional, and nothing else here reaches the false arm.

        Every other GOTO program inverts first, so the register is 1 by the
        time the jump is read and an unconditional jump passes all of them.
        Left alone the register is 0, so the GOTO must fall through to the
        two PUSHes; a jump would land on the second and print one value.
        """
        assert run_and_capture("GOTO 2 PUSH PUSH") == "0 0"

    def test_goto_target_is_zero_based(self) -> None:
        """GOTO N lands on the Nth command counting from zero.

        ``test_goto`` jumps to 2, and the two commands after the GOTO are
        both PUSH -- so landing on either printed the same thing.  Jumping
        to 3 skips the first of them and prints one value instead of two.
        """
        assert run_and_capture("INVERT GOTO 3 PUSH PUSH") == "1"

    @pytest.mark.parametrize(
        "code", ["INVERTPUSH", "PUSHPOP", "GOTO12", "INVERT GOTO 2PUSH"]
    )
    def test_commands_require_whitespace_boundaries(self, code: str) -> None:
        with pytest.raises(ValueError, match="is not a Bitdeque command"):
            run_and_capture(code)

    @pytest.mark.parametrize("separator", [" ", "  ", "\t", "\n", "\r\n"])
    def test_goto_accepts_whitespace_before_its_target(self, separator: str) -> None:
        assert run_and_capture(f"INVERT GOTO{separator}3 INVERT PUSH") == "1"

    def test_inject_adds_to_the_front(self) -> None:
        """INJECT puts the register at the front, where PUSH appends.

        Nothing in the suite used INJECT at all: the token could be spelled
        anything and every test still passed.
        """
        assert run_and_capture("INVERT PUSH INVERT INJECT") == "0 1"
        assert run_and_capture("INVERT PUSH PUSH INVERT INJECT") == "0 1 1"

    def test_push_appends_rather_than_prepending(self) -> None:
        """PUSH works the back, told apart from INJECT rather than from nothing.

        The two assertions above pair a PUSH with an INJECT symmetrically,
        so a build where PUSH *also* prepends produces the same deque and
        passes them -- they pin INJECT against doing nothing, not against
        PUSH.  Three pushes with the register changing partway are not
        symmetric: appending gives 1 1 0 and prepending gives 0 1 1.
        """
        assert run_and_capture("INVERT PUSH PUSH INVERT PUSH") == "1 1 0"

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
        assert run_and_capture("INVERT INVERT PUSH") == "0"


class TestStepMachine:
    def test_step_tracks_cursor_register_and_deque(self) -> None:
        from esolangs.interpreters.io import IO
        from esolangs.interpreters.queue_based.bitdeque import _Machine

        machine = _Machine("INVERT PUSH", IO())
        assert (machine.ind, machine.reg, machine.deq) == (0, 0, ())
        machine.step()  # INVERT flips the register
        assert (machine.ind, machine.reg) == (1, 1)
        machine.step()  # PUSH appends the register
        assert machine.deq == (1,)
        assert machine.halted
        machine.step()  # the post-halt step renders, and moves nothing
        assert machine.ind == 2

    def test_the_deque_renders_once_however_far_it_is_stepped(self) -> None:
        """The post-halt step prints the deque, and only the first one does.

        ``run`` takes exactly one step past the halt, so a render that fired
        on every step past it would look identical there and only show
        through a VM, which is stepped by its caller.  A latch that never
        latched would repeat the output once per extra step.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.queue_based.bitdeque import _Machine

        io_obj = ScriptedIO()
        machine = _Machine("PUSH INVERT", io_obj)
        while not machine.halted:
            machine.step()
        assert io_obj.getvalue() == ""  # nothing until the step past the halt
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
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "PUSH"
    halting_program = "INVERT PUSH"
    looping_program = "INVERT GOTO 1"
    # `rendered` guards the end-of-run deque dump, so it only flips on the
    # step past the halt; it is read either side here, and `ip`/`memory` are
    # what the run moves.
    state_views = ("rendered", "ip", "memory")
    viewing_program = "INVERT PUSH"
    # `rendered` latches on the step *past* the halt, and the check
    # stops at the halt, so no program can move it here.
    constant_views = frozenset({"rendered"})


@pytest.mark.parametrize(
    ("code", "word"),
    [("xPUSH", "xPUSH"), ("x y PUSH", "x"), ("PUSH x INVERT", "x"), ("PUSH x y", "x")],
)
def test_stray_text_is_rejected_with_the_first_invalid_word(
    code: str, word: str
) -> None:
    expected = (
        f"{word!r} is not a Bitdeque command; the commands are "
        "INJECT, PUSH, EJECT, POP, INVERT and GOTO n, in upper case"
    )
    with pytest.raises(ValueError, match="not a Bitdeque command") as caught:
        run_and_capture(code)
    assert str(caught.value) == expected
