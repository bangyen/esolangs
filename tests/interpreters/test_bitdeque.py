import io
from contextlib import redirect_stdout

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.queue_based.bitdeque import run
from tests.fixtures import text
from tests.interpreters.contract import (
    CycleContract,
    SnapshotContract,
    StateViewContract,
)
from tests.raises import assert_rejected_with_hint


def run_and_capture(code: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestBitdeque:
    def test_invert_then_push(self) -> None:
        assert run_and_capture("INVERT PUSH PUSH") == "1 1"

    def test_goto_does_not_jump_on_a_zero_register(self) -> None:
        """GOTO is conditional, and nothing else here reaches the false arm."""
        assert run_and_capture("GOTO 2 PUSH PUSH") == "0 0"

    def test_goto_target_counts_from_one(self) -> None:
        """GOTO 3 lands on the first PUSH; 0-based it would skip to the second."""
        assert run_and_capture("INVERT GOTO 3 PUSH PUSH") == "1 1"
        assert run_and_capture("GOTO 0 PUSH") == "0"
        with pytest.raises(HaltError, match="GOTO 0 names no command"):
            run_and_capture("INVERT GOTO 0 PUSH")

    @pytest.mark.parametrize(
        "code", ["INVERTPUSH", "PUSHPOP", "GOTO12", "INVERT GOTO 2PUSH"]
    )
    def test_commands_require_whitespace_boundaries(self, code: str) -> None:
        with pytest.raises(ValueError, match="is not a Bitdeque command"):
            run_and_capture(code)

    def test_inject_adds_to_the_front(self) -> None:
        """INJECT puts the register at the front, where PUSH appends."""
        assert run_and_capture("INVERT PUSH INVERT INJECT") == "0 1"
        assert run_and_capture("INVERT PUSH PUSH INVERT INJECT") == "0 1 1"

    def test_push_appends_rather_than_prepending(self) -> None:
        """PUSH works the back, told apart from INJECT rather than from nothing."""
        assert run_and_capture("INVERT PUSH PUSH INVERT PUSH") == "1 1 0"

    def test_eject_takes_from_the_front(self) -> None:
        """EJECT pops the front, where POP takes the back."""
        assert run_and_capture("INVERT PUSH INVERT PUSH EJECT PUSH") == "0 1"
        assert run_and_capture("INVERT PUSH INVERT PUSH POP PUSH") == "1 0"

    def test_taking_from_an_empty_deque_gives_zero(self) -> None:
        """POP and EJECT on an empty deque clear the register."""
        assert run_and_capture("INVERT POP PUSH") == "0"
        assert run_and_capture("INVERT EJECT PUSH") == "0"


#: The wiki's Hello, world!, its ``[c] bits:`` labels dropped.
_WIKI_HELLO = text("bitdeque/wiki_hello.txt")


class TestTheWikiExample:
    def test_hello_world_leaves_its_seven_bit_codes_in_the_deque(self) -> None:
        bits = run_and_capture(_WIKI_HELLO).replace(" ", "")
        assert bits == "".join(format(ord(c), "07b") for c in "Hello, world!")

    def test_a_goto_past_the_last_command_ends_the_run(self) -> None:
        assert run_and_capture("INVERT GOTO 9 PUSH") == ""


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
        """The post-halt step prints the deque, and only the first one does."""
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
    looping_program = "INVERT GOTO 2"
    # `rendered` guards the end-of-run deque dump, so it only flips on the
    # step past the halt; it is read either side here, and `ip`/`memory` are
    # what the run moves.
    state_views = ("rendered", "ind", "memory")
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


@pytest.mark.medium
def test_malformed_source_carries_a_repair_hint() -> None:
    assert_rejected_with_hint("Bitdeque", "PUHS", "did you mean 'PUSH'")
