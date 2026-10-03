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
    @pytest.mark.parametrize(
        "code", ["INVERTPUSH", "PUSHPOP", "GOTO12", "INVERT GOTO 2PUSH"]
    )
    def test_commands_require_whitespace_boundaries(self, code: str) -> None:
        with pytest.raises(ValueError, match="is not a Bitdeque command"):
            run_and_capture(code)


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
