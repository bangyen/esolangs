"""Unit tests for the Brainfuck interpreter."""

import importlib

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.brainfuck import _Machine
from esolangs.vm import run_until_halt_or_cycle, run_until_halt_or_growth
from tests.interpreters.contract import CycleContract, EmptyProgramContract
from tests.interpreters.cursorless_io import PositionlessIO
from tests.interpreters.runner import run_program
from tests.reference import REFERENCE
from tests.support.raises import assert_rejected_with_hint

bf = importlib.import_module("esolangs.interpreters.tape_based.brainfuck")


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    """Run a Brainfuck program and return its stdout."""
    return run_program(bf.run, code, "".join(inputs or []))


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
    def test_cell_wraps(self) -> None:
        assert run_and_capture("+" * 256 + ".") == "\x00"

    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            pytest.param("-.", "\xff", id="cell_wraps_below_zero"),
            pytest.param("abc+++abc.abc", "\x03", id="comments_ignored"),
            # +[-] enters a loop, zeroes the cell, and exits.
            pytest.param("+[-].", "\x00", id="loop_zeroing"),
            pytest.param("[.]", "", id="loop_skipped_when_zero"),
            # ++[>+<-] moves 2 from cell 0 to cell 1.
            pytest.param("++[>+<-]>.>.", "\x02\x00", id="loop_iterates_while_nonzero"),
            # A doubly-nested loop leaves a known value in the printed cell.
            pytest.param("+++[>++[>+<-]<-]>+++.", "\x03", id="nested_loop"),
        ],
    )
    def test_output(self, code: str, expected: str) -> None:
        assert run_and_capture(code) == expected

    def test_the_tape_grows_left(self) -> None:
        """< at the left edge adds a fresh cell; the start cell keeps its value."""
        assert run_and_capture("+<<+++.>>.") == "\x03\x01"
        assert run_and_capture("+" + "<" * 100 + ">" * 100 + ".") == "\x01"

    def test_input_echo(self) -> None:
        assert run_and_capture(",>,<.>.", inputs=["A", "B"]) == "AB"

    @pytest.mark.parametrize(
        ("char", "expected"),
        [("Ā", "\x00"), ("ā", "\x01"), ("\U0001f600", "\x00")],
        ids=["256", "257", "emoji"],
    )
    def test_an_input_character_above_255_is_taken_modulo_256(
        self, char: str, expected: str
    ) -> None:
        """``,`` writes a cell, so it reduces like every other write."""
        assert run_and_capture(",.", inputs=[char]) == expected

    def test_a_read_cell_and_an_incremented_one_agree(self) -> None:
        """The bug this pins was a disagreement, not just a wide value."""
        assert run_and_capture(",+.", inputs=["Ā"]) == "\x01"

    def test_machine_exposes_its_state(self) -> None:
        """``ind``/``ptr``/``tape`` track the run and stay in step."""
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


@pytest.mark.medium
def test_malformed_source_carries_a_repair_hint() -> None:
    assert_rejected_with_hint(REFERENCE, "[", "close this '['")


@pytest.mark.parametrize("io_type", [ScriptedIO, PositionlessIO])
@pytest.mark.parametrize(
    ("code", "detector", "output"),
    [
        (",[.,]", run_until_halt_or_cycle, "aaaa"),
        (",[>,]", run_until_halt_or_growth, ""),
    ],
)
def test_cursorless_input_cannot_prove_cycle_or_growth(io_type, code, detector, output):
    io = io_type("aaaa\0")
    machine = _Machine(code, io)
    assert detector(machine, limit=100)
    assert machine.halted
    assert io.getvalue() == output
    assert io.reads == 5
