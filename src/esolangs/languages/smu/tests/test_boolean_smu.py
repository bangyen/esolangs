"""Execution tests for the Smu boolean generator."""

import random

import pytest

import esolangs
from esolangs.languages.smu import generator as tools
from esolangs.languages.smu.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from scripts.docs.evidence import construction_boundaries
from tests.generators.sample_tables import five_input_sample
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import assert_saved_rows, constant_programs


def execute(program: str, row: int, n: int) -> tuple[str, int]:
    io = ScriptedIO(format(row, f"0{n}b"))
    run(program, io)
    return io.getvalue(), io.position()


def test_every_three_input_table_runs_every_row() -> None:
    """Folds, pads and macros all answer, and every table reads all its bytes."""
    for value in range(256):
        table = format(value, "08b")
        program = tools.smu(table)
        for row in range(8):
            assert execute(program, row, 3) == (table[row], 3), (table, row)


@pytest.mark.medium  # constants through n=12 plus terminal witnesses: 1.02s alone
def test_sharing_totals() -> None:
    """A macro is kept only where it is shorter; the totals pin the rule."""
    _check_constants()
    _check_terminal_leaves()
    three = [format(value, "08b") for value in range(256)]
    assert sum(len(tools.smu(table)) for table in three) == 45116
    assert sum(len(tools.smu(table)) for table in five_input_sample()) == 47646
    # Past 44 macros names take a digit, so which ones earn the short names
    # and whether a long name still pays both show in the length.
    wide = format(random.Random(3).getrandbits(1 << 11), f"0{1 << 11}b")
    assert len(tools.smu(wide)) == 2184


def test_macro_break_even_stays_inline() -> None:
    """At (uses - 1) * len == (uses + 2) * len(name) the subtree stays inline.

    The repeated ``(b)m`` costs four characters and is used twice.
    A one-character name would tie the inlined size.
    """
    program = tools.smu("0010101000111010")
    assert program.count("(b)m") == 2
    assert "a(b)ma" not in program


def test_twice_used_subtree_earns_a_two_letter_macro() -> None:
    """The keep rule's +2: a subtree used twice against a two-letter name.

    At n = 11 this seed's tree has a subtree used twice under a two-letter name:
    (2 - 1) * 9 > (2 + 2) * 2 keeps it, while a +3 constant would tie the
    test at 9 and drop it, at +1 character.
    """
    table = format(random.Random(321).getrandbits(1 << 11), f"0{1 << 11}b")
    assert len(tools.smu(table)) == 2150


def test_an_ignored_input_is_one_pad() -> None:
    """Equal halves are ``(X)m``, three characters, not ``(X)(X)n``."""
    inner = "0110100110010110"
    for at in (0, 2):
        low = 4 - at
        table = "".join(
            inner[row >> (low + 1) << low | row & ((1 << low) - 1)] for row in range(32)
        )
        program = tools.smu(table)
        for row in range(32):
            assert execute(program, row, 5) == (table[row], 5), (at, row)
    assert len(tools.smu(inner + inner)) - len(tools.smu(inner)) == 3


def _check_terminal_leaves() -> None:
    from checks.certification.resource_evidence import resource_bounds

    bounds = resource_bounds("Smu")
    workspace = bounds["workspace"].formula

    tables = [
        "".join(str((row.bit_count() % 2) ^ inverted) for row in range(1 << n))
        for n in (1, 2, 4, 8)
        for inverted in (False, True)
    ]
    tables.append("0110100110010110" * 2)  # A leading ignored input is still read.
    for table in tables:
        n = len(table).bit_length() - 1

        for options in ({}, {"width": 1}, {"balance": True}):
            program = esolangs.generate("Smu", table, **options).source
            for row in (0, (1 << n) // 3, (1 << n) - 1):
                io = ReadFirstIO(f"{row:0{n}b}", expected=n)
                machine = _Machine(program, io)
                written = WrittenState(machine.workspace_snapshot())
                steps = runs = 0
                while not machine.halted:
                    runs += machine.fresh
                    machine.step()
                    written.sample(machine.workspace_snapshot())
                    if "" in machine.values:
                        # A terminal dead store must never precede another run.
                        assert not machine.fresh
                    steps += 1
                    assert steps <= 55 * n - 1
                assert "" in machine.values
                assert runs == 8 * n
                assert io.getvalue() == table[row]
                assert io.reads == n
                assert io.past_end == 0
                if n >= 2:
                    assert written.bits <= workspace(n, program)
                following = ScriptedIO(f"{row:0{n}b}" + "QR")
                machine = _Machine(program, following)
                steps = count_steps(machine, 55 * n - 1)
                assert following.getvalue() == table[row]
                assert following.reads == n
                assert following.past_end == 0
                assert following.input_char() == ord("Q")


def _check_constants() -> None:
    assert_analysis_complement("Smu", "decision_layers")
    from checks.certification.resource_evidence import resource_bounds

    bounds = resource_bounds("Smu")
    workspace = bounds["workspace"].formula

    language = esolangs.Language("Smu")
    witnesses = construction_boundaries(language.name)[
        "constant_delimiter_macro_cutoff"
    ]
    for witness in witnesses:
        n, table = witness.arity, witness.table()
        artifact = language.generate(table)
        assert ("W)mW" in artifact.source) == (n == 6)
        assert_saved_rows(language, artifact, table, range(len(table)))

    for n, bit, _options, program in constant_programs("Smu", range(1, 13)):
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            io = ReadFirstIO(f"{row:0{n}b}", expected=n)
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            steps = count_steps(machine, 55 * n - 1, written=written)
            assert steps == 55 * n - 1
            assert io.getvalue() == bit
            assert written.bits <= workspace(n, program)
            assert io.past_end == 0
