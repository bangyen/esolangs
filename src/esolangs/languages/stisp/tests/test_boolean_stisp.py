"""Tests for the Stisp Boolean generator."""

import pytest

import esolangs
from esolangs.languages.stisp.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from scripts.docs.evidence import construction_boundaries
from scripts.docs.resource_evidence import resource_bounds
from tests.support.analysis_support import assert_analysis_complement
from tests.support.execution import run_observed as run
from tests.support.generator_support import (
    assert_saved_rows,
    constant_artifacts,
    three_input_corpus_size,
)

#: Every one- and two-input table; a diagram's folding bugs show here first.
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_results_in_its_answer(table: str) -> None:
    if table == "00":
        _check_constants()
    n = len(table).bit_length() - 1
    template = esolangs.generate("Stisp", table)
    workspace = resource_bounds("Stisp")["workspace"].formula
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        program = esolangs.instantiate("Stisp", template, bits)
        got = run("Stisp", program, timeout=5).output
        assert esolangs.read_answer("Stisp", got) == table[row], (table, row)
        io = ScriptedIO("7")
        machine = _Machine(program.source, io)
        written = WrittenState(machine.workspace_snapshot())
        steps = 0
        while not machine.halted:
            machine.step()
            written.sample(machine.workspace_snapshot())
            steps += 1
            assert io.getvalue() == ""
        assert steps == (1 if len(set(table)) == 1 else n)
        assert written.bits <= workspace(n, program.source)
        before_dump = written.bits
        machine.step()
        written.sample(machine.workspace_snapshot())
        assert written.bits == before_dump + 1
        assert io.getvalue() == table[row]
        assert io.reads == 0
        assert io.input_char() == ord("7")


def test_the_and_template_is_the_documented_one() -> None:
    assert esolangs.generate("Stisp", "0001").source == (
        "(l h)->s[0]=l;(l h)->s[1]=h;c->s[x]=c;(0 (0 1))->s[$]->s[$]"
    )

    language = esolangs.Language("Stisp")
    records = construction_boundaries(language.name)
    for witness in records["constant_scalar_to_list_head"]:
        table = witness.table()
        artifact = language.generate(table)
        assert ("($ $)" in artifact.source) == (witness.arity == 2)
        assert_saved_rows(language, artifact, table, range(len(table)))


def test_an_ignored_input_still_selects_one_of_two_identical_children() -> None:
    assert esolangs.generate("Stisp", "0101").source == (
        "(l h)->s[0]=l;(l h)->s[1]=h;c->s[x]=c;((0 1) (0 1))->s[$]->s[$]"
    )


def _check_constants() -> None:
    assert_analysis_complement("Stisp", "decision_layers")
    assert three_input_corpus_size("Stisp") == 20552
    for n, bit, options, template in constant_artifacts("Stisp", range(1, 13)):
        assert template.source.count("$") == n
        if not options:
            assert len(template.source) == (15 if n == 1 else 2 * n + 15)
        peak = 0
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            bits = list(map(int, f"{row:0{n}b}"))
            program = template.fill(bits)
            io = ScriptedIO("7")
            machine = _Machine(program.source, io)
            head = machine.head
            values = [head] if n == 1 else []
            if n > 1:
                while head != ():
                    value, head = head
                    values.append(value)
            assert values == list(map(str, bits))
            written = WrittenState(machine.workspace_snapshot())
            machine.step()
            written.sample(machine.workspace_snapshot())
            assert machine.halted
            assert machine.head == bit
            assert io.getvalue() == ""
            assert written.bits <= 8 * n + 8
            peak = max(peak, written.bits)
            machine.step()
            written.sample(machine.workspace_snapshot())
            assert io.getvalue() == bit
            assert io.reads == io.past_end == 0
            assert io.input_num() == 7
            assert written.bits <= 8 * n + 9
        assert peak == 8 * n + 8
