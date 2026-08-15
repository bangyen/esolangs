"""Unit tests for the Number Seventy-Four interpreter."""

import io
import os
import signal
from contextlib import redirect_stdout

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.other.number_seventy_four import run


class _TimeoutError(Exception):
    """Raised when the alarm fires: the program did not halt on its own."""


def _on_alarm(_signum: int, _frame: object) -> None:
    raise _TimeoutError("program did not halt")


def run_and_capture(code: str) -> str:
    """Run ``code`` and return its output through a bare ``IO()``."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestSeventyFour:
    def test_zero_then_halt(self) -> None:
        assert run_and_capture("0H") == "H0"

    def test_zeros_push_in_reverse_order(self) -> None:
        assert run_and_capture("000H") == "H000"

    def test_one_and_zero_then_halt(self) -> None:
        assert run_and_capture("10H") == "H01"

    def test_h_on_one_leading_output_does_nothing(self) -> None:
        """An ``H`` after a ``1`` writes nothing; only the later ``0`` lets
        the final ``H`` fire."""
        assert run_and_capture("1H0H") == "H01"

    def test_trailing_h_does_not_fire_twice(self) -> None:
        """Once the output starts with ``H`` it no longer starts with ``0``,
        so a second ``H`` is a no-op and the pass still halts."""
        assert run_and_capture("0HH") == "H0"

    def test_leading_h_on_empty_output_does_nothing(self) -> None:
        assert run_and_capture("H0H") == "H0"

    def test_unknown_characters_are_ignored(self) -> None:
        assert run_and_capture("0xH") == "H0"
        assert run_and_capture("0H\n") == "H0"

    @pytest.mark.skipif(os.name != "posix", reason="signal.alarm is POSIX-only")
    @pytest.mark.parametrize(
        "program",
        [
            "0",
            "1",
            "H",
            "1H",
            "0H0",  # mid-pass ``H`` output is undone by the trailing ``0``
        ],
    )
    def test_output_never_starting_with_h_loops_forever(self, program: str) -> None:
        old_handler = signal.signal(signal.SIGALRM, _on_alarm)
        signal.alarm(2)
        try:
            run(program, IO())
        except _TimeoutError:
            pass
        else:
            pytest.fail(f"{program!r} should restart forever without printing")
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
