"""Tests for the Nandypants Boolean generator."""

import esolangs
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import assert_every_row, three_input_corpus_size
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        if table == "00":
            assert_analysis_complement("Nandypants", "subtree_ids")
            _check_constants()
            _check_forward()
        assert_every_row("Nandypants", table)


def _check_constants() -> None:
    from esolangs.languages.nandypants.interpreter import _Machine
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("Nandypants")["workspace"].formula
    for n in range(1, 13):
        for bit in "01":
            commands = 8 * n + 11 + 2 * int(bit)
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate(
                    "Nandypants", bit * (1 << n), **options
                ).source
                peak = 0
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "Nandypants", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "Q", expected=n)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = count_steps(machine, commands, written=written)
                    assert steps == commands
                    assert io.getvalue() == bit
                    assert io.past_end == 0
                    peak = max(peak, written.bits)
                    assert written.bits == workspace(n, program)
                    assert machine.state.remaining == 0
                    assert io.input_char() == ord("Q")
    assert three_input_corpus_size("Nandypants") == 25214


def _check_forward() -> None:
    from esolangs.languages.nandypants.interpreter import _Machine

    jumped = False
    for table in ("1101001101101101", "00110110", "00011110"):
        n = len(table).bit_length() - 1
        program = esolangs.generate("Nandypants", table).source
        for row in range(len(table)):
            io = ScriptedIO(f"{row:0{n}b}" + "7")
            machine = _Machine(program, io)
            steps = 0
            while not machine.halted:
                before = machine.ip
                if machine.program.tokens[before] == "\\":
                    assert io.reads == n
                    assert machine.state.remaining == 0
                machine.step()
                assert machine.ip > before
                jumped |= machine.ip != before + 1
                steps += 1
                assert steps <= 12 * n + 18
            assert io.getvalue() == table[row]
            assert io.input_char() == ord("7")
    assert jumped
