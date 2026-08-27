"""Unit tests for the ArrowQueue interpreter.

ArrowQueue has no output commands, so the tests assert termination (halting
on an off-grid move or an empty-queue pop) and that the direction queue and
turning mechanics run without error.  Because halting is the only observable,
a program can act as a truth machine: the presence of a command in a chosen
cell decides whether the IP loops forever or runs out of queue and halts.
The truth-machine branch is decided deterministically by state-cycle
detection — the sustaining ring is a finite cycle — so the tests need no
wall-clock bound.
"""

import io
from contextlib import redirect_stdout

import esolangs
from esolangs.interpreters.grid_based.arrowqueue import _Machine, run
from esolangs.interpreters.io import IO
from esolangs.vm import run_until_halt_or_cycle


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


class TestMachineState:
    """Assertions on where the IP ends up, which output cannot show.

    ArrowQueue prints nothing, so a test that only checks ``== ""`` passes
    for any machine that terminates -- turning the wrong way, padding the
    grid on the wrong side, or queueing the wrong heading all look alike.
    These pin the state the empty string hides.
    """

    def final(self, code: list[str]) -> tuple[int, int, int, list[int]]:
        machine = _Machine(code)
        while not machine.halted:
            machine.step()
        return machine.row, machine.col, machine.d, list(machine.queue)

    def test_short_lines_pad_on_the_right(self) -> None:
        """A short line is padded to the right, keeping its content in place.

        ``ljust`` and ``rjust`` agree whenever the short line is the last one
        or holds only no-ops, which is every ragged grid the suite had.  Here
        the ``*`` on the short first row must stay at column 0: padding on
        the left would shift it under the ``+`` and change where the IP goes.
        """
        assert self.final(["*", "~+"]) == (2, 0, 1, [1])

    def test_heading_wraps_after_four_turns(self) -> None:
        """Four turns come back to the start; the heading is one of four.

        Every other program leaves the grid before the fourth ``*``, so a
        heading counted modulo 5 was never reached -- and a fifth heading has
        no delta, so this grid raises IndexError under that mutation instead
        of walking off the edge.
        """
        assert self.final(["~**", "*~*", "***"]) == (-1, 0, 3, [0, 1, 0, 3, 2, 3])

    def test_empty_program_has_no_grid(self) -> None:
        """Code with no lines halts at once on a zero-width, empty grid."""
        machine = _Machine([])
        assert machine.halted
        assert (machine.width, machine.grid) == (0, [])

    def test_truth_machine_present_loops_forever(self) -> None:
        """A ~ in the data cell sustains the ring, so the program never halts."""
        program = [" ~*", "+~*", "*~+"]
        assert run_until_halt_or_cycle(_Machine(program)) is False

    def test_truth_machine_absent_halts(self) -> None:
        """Without the ~, the ring stops refilling and an empty queue halts it."""
        program = [" ~*", "+ *", "*~+"]
        assert run_until_halt_or_cycle(_Machine(program)) is True
