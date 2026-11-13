"""Tests for the Rubic Boolean generator."""

import pytest

import esolangs
from esolangs.languages.rubic.generator import _OPENING, _TABLE
from esolangs.languages.rubic.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.execution import run_observed as run
from tests.support.generator_support import three_input_corpus_size
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        if table == "00":
            assert_analysis_complement("Rubic", "subtree_ids")
        n = len(table).bit_length() - 1
        program = esolangs.generate("Rubic", table).source
        opening = _Machine(" ".join(_OPENING), ScriptedIO())
        while not opening.halted:
            opening.step()

        class ReadFirstIO(ScriptedIO):
            inputs = n

            def _write(self, value):
                assert self.progress() == self.inputs
                super()._write(value)

        for row in range(len(table)):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            stdin = esolangs.encode_inputs("Rubic", bits)
            got = run("Rubic", program, stdin=stdin, timeout=5).output
            io = ReadFirstIO(stdin + "Q")
            machine = _Machine(program, io)
            while not machine.halted:
                machine.step()
            assert machine.state.cube == opening.state.cube
            assert io.getvalue() == table[row]
            assert io.progress() == n
            assert io.past_end == 0
            assert io.input_char() == ord("Q")
            # The answer as the contract reads it, not the raw output.
            assert esolangs.read_answer("Rubic", got) == table[row], (table, row)


def test_the_table_holds_on_both_cube_states() -> None:
    """The totality certificate: the cube is the opening's X or X·r2, and
    every expression the generator emits has its stated value on both."""

    def out(*tokens: str) -> str:
        return run("Rubic", " ".join(tokens)).output

    for store in ((), ("r2",)):
        state = (*_OPENING, *store)
        assert out(*state, *_TABLE["read"][:2], "!") == chr(127)  # V = -1
        assert out(*state, *_TABLE["print0"]) == "0"
        assert out(*state, *_TABLE["print1"]) == "1"
        for bit in (0, 1):
            setter = _TABLE[f"print{bit}"][:-1]
            assert out(*state, *setter, *_TABLE["bit"], "!") == chr(bit)
        y = len(store)
        expression = _Machine(" ".join((*state, *_TABLE["not"])), ScriptedIO())
        while not expression.halted:
            expression.step()
        assert expression.state.v == 49 - y
        assert out(*state, *_TABLE["P"], "!") == chr(y)
        assert out(*state, *_TABLE["Q"], "!") == chr(1 - y)


@pytest.mark.medium
def test_constant_reads_precede_output_and_preserve_the_next_character() -> None:
    for n in range(1, 13):
        for bit in "01":
            commands = n + 11
            workspace = (
                119
                + (n + 11).bit_length()
                + (n + 5).bit_length()
                + (n + 6).bit_length()
                + n.bit_length()
            )
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Rubic", bit * (1 << n), **options).source
                if not options:
                    assert len(program) == 2 * n + 35
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "Rubic", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "Q", expected=n)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = count_steps(machine, commands, written=written)
                    assert steps == commands
                    assert written.bits == workspace
                    assert io.getvalue() == bit
                    assert io.input_char() == ord("Q")
    assert three_input_corpus_size("Rubic") == 63126
