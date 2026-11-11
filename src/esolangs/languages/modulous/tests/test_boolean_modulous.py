"""modulous generator tests."""

import random

import pytest

import esolangs
from esolangs.exceptions import InputExhaustedError
from esolangs.languages.modulous import generator as boolean
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from scripts.docs.evidence import construction_boundaries
from tests.generators.boolean_runners import _runner
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import (
    assert_an_ignored_input_costs,
    assert_saved_rows,
    measure_run,
    three_input_corpus_size,
)
from tests.support.witness_tables import witnesses

run_modulous = _runner("modulous", newline=True)


class TestModulous:
    @pytest.mark.parametrize("width", [1, 4, 7, 13, 40, 80])
    def test_narrow_chunks_execute_every_small_table(self, width: int) -> None:
        if width == 4:
            language = esolangs.Language("Modulous")
            records = construction_boundaries(language.name)
            for witness in records["integer_to_string_chunk_width"]:
                table = witness.table()
                for columns, value_type in ((3, "INT"), (4, "STR")):
                    artifact = language.generate(table, width=columns)
                    assert artifact.source.split()[2] == value_type
                    assert_saved_rows(language, artifact, table, range(len(table)))

        for n in range(1, 4):
            for table in witnesses(n):
                program = esolangs.generate("Modulous", table, width=width).source
                assert max(map(len, program.splitlines())) <= max(width, 4)
                for row in range(2**n):
                    bits = list(format(row, f"0{n}b"))
                    assert run_modulous(program, bits) == table[row]

    @pytest.mark.medium
    @pytest.mark.parametrize("n", [5, 8])
    def test_narrow_chunks_and_relative_jumps_at_larger_arity(self, n: int) -> None:
        rng = random.Random(20260930 + n)
        for table in (
            "".join(str(row.bit_count() & 1) for row in range(2**n)),
            format(rng.getrandbits(2**n), f"0{2**n}b"),
        ):
            for width in (1, 4, 13, 80):
                program = esolangs.generate("Modulous", table, width=width).source
                for row in [0, 2**n - 1, *rng.sample(range(2**n), 12)]:
                    assert (
                        run_modulous(program, list(format(row, f"0{n}b"))) == table[row]
                    )

    def test_narrow_literal_floor_and_corpus_size(self) -> None:
        assert max(map(len, boolean.modulous("0110", 1).splitlines())) == 3
        assert (
            sum(len(boolean.modulous(format(v, "08b"), 1)) for v in range(256)) == 71908
        )


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """``[INP INT][POP]``."""
    from tests.generators.generator_sections import named_table

    assert_analysis_complement("Modulous", "input_weights")
    assert_analysis_complement(
        "Modulous", "input_weights", named_table(6, "random 1847")
    )
    assert_analysis_complement("Modulous", "symmetric_weights", "0110100110010110")
    _check_pair_resources()
    assert_an_ignored_input_costs("Modulous", 6, 14)

    from esolangs.languages.modulous.interpreter import _Machine

    base = "11100110001111100101010001000110"
    table = "".join(
        base[
            ((row >> 6 & 1) << 4)
            | ((row >> 4 & 1) << 3)
            | ((row >> 3 & 1) << 2)
            | ((row >> 1 & 1) << 1)
            | (row & 1)
        ]
        for row in range(128)
    )
    for options in ({}, {"width": 1}, {"balance": True}):
        program = esolangs.generate("Modulous", table, **options).source
        for row in range(128):
            io = ScriptedIO("\n".join(f"{row:07b}") + "\n7")
            machine = _Machine(program, io)
            while not machine.halted:
                if machine.tokens[machine.ind].startswith("PRT"):
                    assert io.reads == 7
                machine.step()
            assert io.getvalue() == table[row]
            assert io.input_token() == "7"


@pytest.mark.medium
def test_constants_read_first_within_bounds_and_keep_a_sentinel() -> None:
    from esolangs.languages.modulous.interpreter import _Machine
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("Modulous")["workspace"].formula

    for n in range(1, 13):
        if n == 1:
            for table in ("01", "10"):
                for options in ({}, {"width": 1}, {"balance": True}):
                    program = esolangs.generate("Modulous", table, **options).source
                    for bit in "01":
                        io = ReadFirstIO(bit + "\nQ", expected=n)
                        machine = _Machine(program, io)
                        written = WrittenState(machine.workspace_snapshot())
                        steps = 0
                        while not machine.halted and steps < 8:
                            machine.step()
                            written.sample(machine.workspace_snapshot())
                            steps += 1
                        assert machine.halted
                        assert io.getvalue() == table[int(bit)]
                        assert steps == (4 if table == "01" else 6 + int(bit))
                        assert written.bits <= 13
                        assert io.input_token() == "Q"
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate(
                    "Modulous", bit * (1 << n), **options
                ).source
                if not options and n == 8:
                    assert len(program) == 138
                rows = range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1)
                for row in rows:
                    stdin = esolangs.encode_inputs(
                        "Modulous", list(map(int, format(row, f"0{n}b")))
                    )
                    io = ReadFirstIO(stdin + "Q", expected=n)
                    machine = _Machine(program, io)
                    steps, written = measure_run(machine, limit=2 * n + 3)
                    assert machine.halted
                    assert io.getvalue() == bit
                    assert steps == 2 * n + 3
                    assert written.bits <= workspace(n, program)
                    assert io.input_token() == "Q"
    assert three_input_corpus_size("Modulous") == 37030


def _check_pair_resources() -> None:
    from esolangs.languages.modulous.interpreter import _Machine
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("Modulous")["workspace"].formula

    bounds = resource_bounds("Modulous")
    execution = bounds["execution"].formula
    from esolangs.languages.modulous.tests.formulas import resource_witness

    for n in range(2, 9):
        table = resource_witness(n)
        for options in ({}, {"width": 1}, {"balance": True}):
            program = str(esolangs.generate("Modulous", table, **options).source)
            row = (1 << n) - 1
            io = ScriptedIO("\n".join(f"{row:0{n}b}") + "\nQ")
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            steps = 0
            bound = execution(n, program)
            while not machine.halted:
                if machine.tokens[machine.ind].startswith("PRT"):
                    assert io.reads == n
                machine.step()
                written.sample(machine.workspace_snapshot())
                steps += 1
                assert steps <= bound
            assert io.getvalue() == table[row]
            assert io.reads == n
            assert io.input_token() == "Q"
            assert written.bits <= workspace(n, program)
            if not options:
                assert steps == bound
                assert written.bits == workspace(n, program)
    program = str(esolangs.generate("Modulous", "0010").source)
    machine = _Machine(program, ScriptedIO("0\n"))

    def finish() -> None:
        while not machine.halted:
            machine.step()

    with pytest.raises(InputExhaustedError):
        finish()

    table = resource_witness(5)
    mutant = str(esolangs.generate("Modulous", table).source).replace(
        "[SUB 3]", "[SUB 2]"
    )
    io = ScriptedIO("1\n" * 5)
    machine = _Machine(mutant, io)
    for _ in range(40):
        if machine.halted:
            break
        machine.step()
    assert machine.halted
    assert io.getvalue() != table[-1]
