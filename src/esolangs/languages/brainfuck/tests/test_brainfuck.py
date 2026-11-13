"""Unit tests for the Brainfuck interpreter."""

import importlib
from itertools import product

import pytest

from esolangs import ExecutionLimits
from esolangs.languages.brainfuck.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import run_until_halt_or_cycle, run_until_halt_or_growth
from tests.interpreters.contract import CycleContract, EmptyProgramContract
from tests.interpreters.cursorless_io import PositionlessIO
from tests.interpreters.runner import run_program
from tests.support.raises import assert_rejected_with_hint
from tests.support.reference import REFERENCE

bf = importlib.import_module("esolangs.languages.brainfuck.interpreter")


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    """Run a Brainfuck program and return its stdout."""
    return run_program(bf.run, code, "".join(inputs or []))


def _machine(code: str) -> object:
    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, CycleContract):
    """The shared shapes, with brainfuck's own programs. `+[]` loops."""

    run = staticmethod(run_and_capture)
    machine = staticmethod(_machine)
    halting_program = "+++[>+++<-]>."
    looping_program = "+[]"


class TestBrainfuck:
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

    def test_input_echo(self, monkeypatch) -> None:
        assert run_and_capture(",>,<.>.", inputs=["A", "B"]) == "AB"
        from tests.support.prepared_support import check_image_reuse

        check_image_reuse(REFERENCE, ",.", bf._Program, "parse", monkeypatch)
        _check_lazy_native_plan(monkeypatch)

    def test_a_read_cell_and_an_incremented_one_agree(self) -> None:
        """The bug this pins was a disagreement, not just a wide value."""
        assert run_and_capture(",+.", inputs=["Ā"]) == "\x01"

    def test_machine_exposes_its_state(self) -> None:
        """``ind``/``ptr``/``tape`` track the run and stay in step."""
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
        with pytest.raises(ValueError, match="unmatched"):
            run_and_capture("[")
        with pytest.raises(ValueError, match="unmatched"):
            run_and_capture("]")


@pytest.mark.medium
def test_malformed_source_carries_a_repair_hint() -> None:
    assert_rejected_with_hint(REFERENCE, "[", "close this '['")
    from .test_semantic_oracle import _corpus
    from .workspace_checks import check_workspace_brainfuck

    check_workspace_brainfuck(_corpus)


@pytest.mark.parametrize("io_type", [ScriptedIO, PositionlessIO])
@pytest.mark.parametrize(
    ("code", "detector", "output"),
    [
        (",[.,]", run_until_halt_or_cycle, "aaaa"),
        (",[>,]", run_until_halt_or_growth, ""),
    ],
)
def test_cursorless_input_cannot_prove_cycle_or_growth(
    io_type, code, detector, output
) -> None:
    io = io_type("aaaa\0")
    machine = _Machine(code, io)
    assert detector(machine, limit=100)
    assert machine.halted
    assert io.getvalue() == output
    assert io.reads == 5


def test_compiled_transition_preserves_borrowed_tape_and_reports_effects() -> None:
    from esolangs.languages.brainfuck.interpreter import _advance_compiled, _compile

    tape = bytearray([3])
    state = (0, 0)
    ops = _compile("[>++<-]")
    first = _advance_compiled(state, ops, tape)
    assert _advance_compiled(state, ops, tape) == first
    assert state == (0, 0)
    assert tape == bytearray([3])
    assert first == ((1, 0), (0, 1, ((1, 6), (0, 0))), None, False)
    ops = _compile(",")
    assert _advance_compiled(state, ops, tape)[3]
    assert _advance_compiled(state, ops, tape, 65) == (
        (1, 0),
        (0, 0, ((0, 65),)),
        None,
        False,
    )


@pytest.mark.medium
def test_ordered_reads_retain_four_stores_at_one_cursor() -> None:
    states = []
    for prefix in product("01", repeat=2):
        io = ScriptedIO("".join((*prefix, "0")))
        machine = _Machine(",>,>,<<.", io)
        while io.reads < 2:
            machine.step()
        states.append(machine.snapshot())
        while not machine.halted:
            machine.step()
        assert io.getvalue() == prefix[0]
    assert len(set(states)) == 4
    assert len({state[0] for state in states}) == 1


def _check_lazy_native_plan(monkeypatch):
    import esolangs
    from esolangs.runtime import brackets
    from esolangs.vm import complete_vm

    matched, compiled = [], []
    match = brackets.match_brackets
    compile_ops = bf._compile_ops

    def counted_match(code):
        matched.append(code)
        return match(code)

    def counted_compile(code, partners):
        compiled.append(code)
        return compile_ops(code, partners)

    code = ",[>+<-]>."
    with monkeypatch.context() as patch:
        patch.setattr(brackets, "match_brackets", counted_match)
        patch.setattr(bf, "_compile_ops", counted_compile)
        prepared = esolangs.Language(REFERENCE).prepare(code)
        assert matched == [code]
        assert compiled == []
        machine = prepared.make_vm(stdin="A")
        assert complete_vm(machine) == "A"
        assert compiled == []
        for value in ("A", "Z", "Q"):
            assert prepared.run(stdin=value).output == value
        assert matched == compiled == [code]
        assert (
            prepared.run(stdin="B", limits=ExecutionLimits(max_steps=1000)).output
            == "B"
        )
        assert matched == compiled == [code]
    program = bf._Program.parse(code)
    with pytest.raises(TypeError):
        program.brackets[1] = 0
