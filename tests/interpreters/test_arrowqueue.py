"""Unit tests for the ArrowQueue interpreter.

ArrowQueue has no output commands, so the tests assert termination (halting
on an off-grid move or an empty-queue pop) and that the direction queue and
turning mechanics run without error.  Because halting is the only observable,
a program can act as a truth machine: the presence of a command in a chosen
cell decides whether the IP loops forever or runs out of queue and halts.
"""

import io
import os
import signal
from contextlib import redirect_stdout

import pytest

import esolangs
from esolangs.interpreters.grid_based.arrowqueue import run
from esolangs.interpreters.io import IO


class _TimeoutError(Exception):
    """Raised when the alarm fires: the program did not halt on its own."""


def _on_alarm(_signum: int, _frame: object) -> None:
    raise _TimeoutError("program did not halt")


def run_and_capture(code: list[str]) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestArrowQueue:
    def test_empty_program(self) -> None:
        assert run_and_capture([]) == ""

    def test_empty_line_halts_immediately(self) -> None:
        assert run_and_capture([""]) == ""

    def test_noop_ignored_until_off_grid(self) -> None:
        assert run_and_capture(["   "]) == ""

    def test_star_turns_clockwise(self) -> None:
        assert run_and_capture(["*"]) == ""

    def test_tilde_enqueues_direction(self) -> None:
        assert run_and_capture(["~"]) == ""

    def test_plus_pops_queue(self) -> None:
        assert run_and_capture(["~+"]) == ""

    def test_plus_on_empty_queue_halts(self) -> None:
        assert run_and_capture(["+"]) == ""

    def test_padding_pads_short_lines(self) -> None:
        assert run_and_capture(["~*", "* "]) == ""

    def test_queued_direction_changes_course(self) -> None:
        """The dequeued direction, not the current one, guides the next step."""
        assert run_and_capture(["~*+", "  *"]) == ""

    def test_registered_interpreter_runs(self) -> None:
        assert esolangs.run("ArrowQueue", "~*+") == ""

    @pytest.mark.skipif(os.name != "posix", reason="signal.alarm is POSIX-only")
    def test_truth_machine_present_loops_forever(self) -> None:
        """A ~ in the data cell sustains the ring, so the program never halts."""
        program = [" ~*", "+~*", "*~+"]
        old_handler = signal.signal(signal.SIGALRM, _on_alarm)
        signal.setitimer(signal.ITIMER_REAL, 0.2)
        try:
            run(program, IO())
        except _TimeoutError:
            pass
        else:
            pytest.fail("the ~ branch of the truth machine should never halt")
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    @pytest.mark.skipif(os.name != "posix", reason="signal.alarm is POSIX-only")
    def test_truth_machine_absent_halts(self) -> None:
        """Without the ~, the ring stops refilling and an empty queue halts it."""
        program = [" ~*", "+ *", "*~+"]
        signal.signal(signal.SIGALRM, _on_alarm)
        signal.setitimer(signal.ITIMER_REAL, 0.2)
        try:
            run(program, IO())
        except _TimeoutError:
            pytest.fail("the absent branch of the truth machine should halt")
        finally:
            signal.alarm(0)
