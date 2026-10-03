"""Unit tests for the bit~ interpreter."""

import io
from contextlib import redirect_stdout

from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.tape_based.bit_tilde import run
from tests.interpreters.contract import (
    CycleContract,
    SnapshotContract,
    StateViewContract,
)
from tests.raises import raises_message


def run_and_capture(code: str) -> str:
    """Run ``code`` and return its output through a bare ``IO()``."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


def run_scripted(code: str, stdin: str = "") -> str:
    """Run ``code`` with ``stdin`` as input, returning the captured output."""
    io_obj = ScriptedIO(stdin)
    run(code, io_obj)
    return io_obj.getvalue()


class TestBitTilde:
    def test_single_toggle_prints_most_significant_bit(self) -> None:
        """Cell 0 is the MSB, so one toggle prints 0x80."""
        assert run_and_capture("~(") == "\x80"

    def test_unmatched_bracket_message_is_exact(self) -> None:
        """The message itself is pinned, not just a substring of it.

        Both cases above use ``match=``, which is a substring search, so
        the text could be rewritten around the word "unmatched" and still
        pass.  One scan raises for both directions, so asserting it once
        from each side covers the message wherever it comes from.

        The two sides now read differently, which is the point of the
        shared rejection in :mod:`~esolangs.interpreters.brackets`: the
        message names the loose bracket and where it stands, so the ``{``
        case and the ``}`` case are told apart by it.  The position is the
        bracket the scan set out from, not where the walk ran off the code.
        """
        for code, message in (
            ("{~", "unmatched '{' at position 0"),
            ("~}", "unmatched '}' at position 1"),
        ):
            with raises_message(ValueError, message):
                run_and_capture(code)


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.bit_tilde import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract, StateViewContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "~("
    halting_program = "~("
    looping_program = "~{}"
    state_views = ("ind", "cell", "memory")
    # Walks out far enough to flip a cell and come back, so `cell`
    # moves rather than only the cursor.
    viewing_program = ">>>>>>>~<<<<<<<("
