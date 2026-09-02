"""Hang-detection tests for APL, kept apart from the interpreter's own.

These import :mod:`esolangs.vm`, which drops the whole module from the
mutation bundle (``docs/roadmap.md``, "Naming ``esolangs.vm`` ... drops
the test").  Keeping them in their own file means only these tests are
dropped, rather than the interpreter's entire suite -- so a survivor in
``snapshot()`` or ``step()`` still names a real gap.
"""

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.algebraic_programming_language import _Machine
from esolangs.vm import run_until_halt_or_ancestor, run_until_halt_or_cycle

TRUTH_MACHINE = "x? = x & x?\nn?"


def machine(program: str, stdin: str = "") -> _Machine:
    """Build a machine for the detectors to step."""
    return _Machine(program, ScriptedIO(stdin))


class TestHangDetection:
    """The truth machine is the shape the explicit frame stack exists for."""

    def test_a_halting_program_is_reported_as_halting(self) -> None:
        assert run_until_halt_or_cycle(machine("1 + 1")) is True

    def test_the_truth_machine_halts_on_zero(self) -> None:
        assert run_until_halt_or_ancestor(machine(TRUTH_MACHINE, "0\n")) is True

    def test_the_truth_machine_is_proven_to_hang_on_one(self) -> None:
        """Each lap re-enters ``?`` with the same binding and input cursor.

        ``run_until_halt_or_cycle`` cannot catch this: the frame stack
        grows forever, so no whole-machine snapshot ever repeats.
        """
        assert run_until_halt_or_ancestor(machine(TRUTH_MACHINE, "1\n")) is False

    def test_a_recursion_whose_bindings_differ_each_lap_is_undecided(self) -> None:
        """The check proves *repeats*, not every infinite recursion.

        ``F(x) = F(x + 1)`` enters with a new binding every lap, so no
        frame ever replays an ancestor and the walk exhausts its budget
        rather than returning a verdict -- the documented limit that
        keeps a wall-clock backstop necessary.
        """
        import pytest

        with pytest.raises(TimeoutError):
            run_until_halt_or_ancestor(machine("F(x) = F(x + 1)\nF(0)"))
