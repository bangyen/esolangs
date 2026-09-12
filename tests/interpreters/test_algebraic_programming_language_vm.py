r"""Hang-detection tests for APL, kept apart from the interpreter's own."""

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.algebraic_programming_language import _Machine
from esolangs.vm import run_until_halt_or_ancestor, run_until_halt_or_cycle

TRUTH_MACHINE = "x? = x & x?\nn?"


def machine(program: str, stdin: str = "") -> _Machine:
    r"""Build a machine for the detectors to step."""
    return _Machine(program, ScriptedIO(stdin))


class TestHangDetection:
    r"""The truth machine is the shape the explicit frame stack exists for."""

    def test_a_halting_program_is_reported_as_halting(self) -> None:
        assert run_until_halt_or_cycle(machine("1 + 1")) is True

    def test_the_truth_machine_halts_on_zero(self) -> None:
        assert run_until_halt_or_ancestor(machine(TRUTH_MACHINE, "0\n")) is True

    def test_the_truth_machine_is_proven_to_hang_on_one(self) -> None:
        r"""Each lap re-enters ``?`` with the same binding and input cursor."""
        assert run_until_halt_or_ancestor(machine(TRUTH_MACHINE, "1\n")) is False

    def test_a_recursion_whose_bindings_differ_each_lap_is_undecided(self) -> None:
        r"""The check proves *repeats*, not every infinite recursion."""
        import pytest

        with pytest.raises(TimeoutError):
            run_until_halt_or_ancestor(machine("F(x) = F(x + 1)\nF(0)"))
