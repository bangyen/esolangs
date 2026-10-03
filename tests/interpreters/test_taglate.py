"""Unit tests for the Taglate interpreter.

Taglate is a queue-based language: the first line seeds a queue of integers
(0-65535, wrapping), and the remaining lines hold commands (arithmetic,
rotate/discard, loops, character I/O, the ``j`` counter trick, and the
Google Translate URL ``t`` command).
"""

from typing import ClassVar

import pytest

import esolangs
from esolangs.interpreters.queue_based.taglate import run
from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.interpreters.runner import run_program
from tests.raises import raises_message


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


class TestTaglate:
    def test_a_literal_line_is_printed_by_one_i_per_character(self) -> None:
        """``i`` advances one character of the line above it."""
        program = "Hello, World!\niiiiiiiiiiiii"
        assert esolangs.run("Taglate", program) == "Hello, World!"

    def test_unmatched_loop_markers_rejected(self) -> None:
        """An unmatched gy/gz is a malformed program.

        ``match=`` is a substring search, and both messages contain the
        word it looks for -- so each is asserted whole here, since the
        message is the only thing that says which marker was the loose
        one.

        The position is the *token* index rather than a character offset,
        because a Taglate program is a token list; the shared rejection in
        :mod:`~esolangs.interpreters.brackets` names whatever the language
        counts in.
        """
        with raises_message(ValueError, "unmatched 'gy' at position 0"):
            run_and_capture(["\x001", "gy"])

        with raises_message(ValueError, "unmatched 'gz' at position 0"):
            run_and_capture(["1", "gz"])


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.queue_based.taglate import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program: ClassVar[list[str]] = ["abc", "i"]
    halting_program: ClassVar[list[str]] = ["abc", "i"]
    looping_program: ClassVar[list[str]] = ["1", "gy", "gz"]


class TestTheTwoQueueLanguagesDifferOnPurpose:
    """Public API rejects unknown Bitdeque words while preserving valid output."""

    def test_bitdeque_refuses_a_word_it_does_not_know(self) -> None:
        """``findall`` kept what matched and dropped the rest in silence."""
        with pytest.raises(esolangs.ProgramError, match="not a Bitdeque command"):
            esolangs.run("Bitdeque", "PUSH FROB PUSH", "", 5)

    def test_bitdeque_refuses_the_lower_case_program(self) -> None:
        """The whole language was a no-op for anyone who guessed the case.

        Case-sensitivity had never been written down either, so this exited
        0 having done nothing -- indistinguishable from a program that
        legitimately prints nothing.
        """
        with pytest.raises(esolangs.ProgramError, match="upper case"):
            esolangs.run("Bitdeque", "push invert push", "", 5)

    def test_bitdeque_still_runs_a_real_program(self) -> None:
        """Three refusals are worth nothing if the valid case broke."""
        assert esolangs.run("Bitdeque", "PUSH INVERT PUSH", "", 5) == "0 1"
