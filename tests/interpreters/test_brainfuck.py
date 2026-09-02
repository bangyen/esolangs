"""Unit tests for the Brainfuck interpreter.

The interpreter pins the wrapping tape, ``<`` clamp, and bracket-matching
loop semantics directly.
"""

import importlib

from tests.interpreters.contract import CycleContract, EmptyProgramContract
from tests.interpreters.runner import run_program

bf = importlib.import_module("esolangs.interpreters.tape_based.brainfuck")


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    """Run a Brainfuck program and return its stdout.

    ``inputs`` stays a list of lines because that is what this file's
    ``,`` tests read most naturally; the shared runner takes the joined
    stdin, so the join happens here.
    """
    return run_program(bf.run, code, "".join(f"{line}\n" for line in inputs or []))


def _machine(code: str) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.brainfuck import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, CycleContract):
    """The shared shapes, with brainfuck's own programs. `+[]` loops."""

    run = staticmethod(run_and_capture)
    machine = staticmethod(_machine)
    halting_program = "+++[>+++<-]>."
    looping_program = "+[]"


class TestBrainfuck:
    def test_output_character(self) -> None:
        assert run_and_capture("+" * 65 + ".") == "A"

    def test_cell_wraps(self) -> None:
        assert run_and_capture("+" * 256 + ".") == "\x00"

    def test_cell_wraps_below_zero(self) -> None:
        # The upward wrap above lands on zero for any modulus, so it pins
        # neither the wrap's direction nor its width.  Decrementing from
        # zero does: it is 255 only under a modulus of exactly 256.
        assert run_and_capture("-.") == "\xff"

    def test_comments_ignored(self) -> None:
        assert run_and_capture("abc+++abc.abc") == "\x03"

    def test_movement(self) -> None:
        assert run_and_capture("++>++<.>.>") == "\x02\x02"

    def test_left_clamped(self) -> None:
        """< at the left edge does nothing (the tape is clamped there)."""
        assert run_and_capture("<<.") == "\x00"

    def test_input_echo(self) -> None:
        assert run_and_capture(",>,<.>.", inputs=["A", "B"]) == "AB"

    def test_loop_zeroing(self) -> None:
        """+[-] enters a loop, zeroes the cell, and exits."""
        assert run_and_capture("+[-].") == "\x00"

    def test_loop_skipped_when_zero(self) -> None:
        assert run_and_capture("[.]") == ""

    def test_loop_iterates_while_nonzero(self) -> None:
        """++[>+<-] moves 2 from cell 0 to cell 1."""
        assert run_and_capture("++[>+<-]>.>.") == "\x02\x00"

    def test_nested_loop(self) -> None:
        """A doubly-nested loop leaves a known value in the printed cell."""
        assert run_and_capture("+++[>++[>+<-]<-]>+++.") == "\x03"

    def test_machine_exposes_its_state(self) -> None:
        """``ind``/``ptr``/``tape`` track the run and stay in step.

        The three are views onto one immutable state rather than fields
        that are assigned separately, and they are the surface ``vm.py``
        reads off the machine (``ip``, ``memory``) -- so a state that
        stopped being rebound, or a view that went stale, would show up
        here rather than as a wrong answer somewhere downstream.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainfuck import _Machine

        machine = _Machine(">+>++", ScriptedIO())
        assert (machine.ind, machine.ptr, machine.tape) == (0, 0, (0,))

        for _ in range(3):  # ">+>" -- grow, write, grow again
            machine.step()
        assert (machine.ind, machine.ptr, machine.tape) == (3, 2, (0, 1, 0))

        while not machine.halted:
            machine.step()
        assert (machine.ind, machine.ptr, machine.tape) == (5, 2, (0, 1, 2))

    def test_unmatched_bracket_rejected(self) -> None:
        """Unbalanced brackets are a malformed program, not a halt."""
        import pytest

        with pytest.raises(ValueError, match="unmatched"):
            run_and_capture("[")
        with pytest.raises(ValueError, match="unmatched"):
            run_and_capture("]")
        with pytest.raises(ValueError, match="unmatched"):
            run_and_capture("+]")
