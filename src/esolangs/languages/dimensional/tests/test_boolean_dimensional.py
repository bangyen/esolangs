"""Dimensional generator tests."""

import random
from unittest.mock import patch

import pytest

import esolangs
from esolangs import run
from esolangs.generation.helpers import input_weights
from esolangs.generation.wrap import (
    wrap_program,
)
from esolangs.languages.dimensional import generator as boolean
from esolangs.languages.dimensional.generator import _packed, dimensional
from esolangs.languages.dimensional.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from scripts.docs.evidence import construction_boundaries
from tests.generators.boolean_runners import _runner
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import (
    assert_saved_rows,
    constant_programs,
    evaluate_generated,
)
from tests.support.witness_tables import row_bits, witnesses

run_dimensional = _runner("dimensional", newline=True)


@pytest.mark.parametrize("n", [1, 2, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_reads_into_scratch_and_prints_a_fresh_literal(
    n: int, bit: str
) -> None:
    if n == 1 and bit == "0":
        _check_constants()
    table = bit * (1 << n)
    programs = [
        esolangs.generate("Dimensional", table, width=w).source for w in (None, 1, 20)
    ]
    programs.append(esolangs.generate("Dimensional", table, balance=True).source)
    for program in programs:
        for row in range(1 << n):
            io = ScriptedIO("\n".join(f"{row:0{n}b}") + "\nextra")
            machine = _Machine(program, io)
            for _ in range(1000):
                if machine.halted:
                    break
                machine.step()
            assert machine.halted
            assert (io.getvalue(), io.reads) == (bit, n)


@pytest.mark.medium
def test_bare_axis_leaves_execute_all_small_tables() -> None:
    language = esolangs.Language("dimensional")
    cases = construction_boundaries(language.name)["width_one_bare_axis_cutoff"]
    for witness in cases:
        table = witness.table()
        with patch.object(
            boolean, "_dimensional_bare", wraps=boolean._dimensional_bare
        ) as route:
            artifact = language.generate(table, width=1)
        assert route.call_count == int(witness.arity == 2)
        assert_saved_rows(language, artifact, table, range(len(table)))

    for n in range(1, 4):
        for table in witnesses(n):
            program = esolangs.generate("Dimensional", table, width=1).source
            assert max(map(len, program.splitlines())) == (1 if n <= 2 else 2)
            for row, expected in enumerate(table):
                io = ScriptedIO("\n".join(format(row, f"0{n}b")))
                machine = _Machine(program, io)
                for _ in range(5000):
                    if machine.halted:
                        break
                    machine.step()
                assert machine.halted
                assert (io.getvalue(), io.reads) == (expected, n)
    # Ignored inputs paint nothing: 0011 ignores the second, 0101 the first.
    xor = len(dimensional("0110", 1))
    assert len(dimensional("0011", 1)) < xor
    assert len(dimensional("0101", 1)) < xor


@pytest.mark.parametrize("width", [None, 2, 3, 8, 80])
def test_other_widths_preserve_the_established_build(width: int | None) -> None:
    for table in ("00", "11", "0110", "0001", "10010110"):
        assert dimensional(table, width) == wrap_program(
            dimensional(table), "dimensional", width
        )


@pytest.mark.parametrize("n", [4, 6])
def test_larger_tables_keep_the_established_index(n: int) -> None:
    if n == 4:
        _check_first_essential_read()
    table = "".join(str((row * 73 + row // 3) & 1) for row in range(1 << n))
    program = esolangs.generate("Dimensional", table, width=1).source
    for row in (0, 1, len(table) // 2, len(table) - 1):
        io = ScriptedIO("\n".join(format(row, f"0{n}b")))
        machine = _Machine(program, io)
        for _ in range(50_000):
            if machine.halted:
                break
            machine.step()
        assert machine.halted
        assert (io.getvalue(), io.reads) == (table[row], n)


class TestDimensional:
    def test_a_bare_move_is_the_addressing(self) -> None:
        """A bare >/< takes its dimension from the cell, which is the point."""
        assert_analysis_complement("Dimensional", "input_weights", "0001")
        from esolangs.generation.lookup import change_points

        assert boolean.change_points is change_points
        with patch.object(boolean, "change_points", return_value=[]) as corrupted:
            assert evaluate_generated("Dimensional", "0001") == "0000"
            assert corrupted.called
        program = boolean.dimensional("0110")
        bare = [
            i
            for i, c in enumerate(program)
            if c in "><" and not program[i + 1 :][:1].isdigit()
        ]
        assert len(bare) == 4, program  # two painted ones, two d> reads

    def test_the_table_costs_two_characters_an_entry(self) -> None:
        """One painted cell an entry, whichever bit, until a zero run is a loop."""
        full = "0" + "1" * 63
        spaced = "01" * 31 + "11"
        rng = random.Random(7)
        alternating, other = (
            "".join(rng.choice("01") for _ in range(64)) for _ in range(2)
        )
        one = "0" * 63 + "1"
        assert len(boolean.dimensional(alternating)) == len(boolean.dimensional(other))
        assert len(boolean.dimensional(one)) < len(boolean.dimensional(alternating))
        # A ones-heavy table is painted as its complement, a zero run.
        assert len(boolean.dimensional(full)) < len(boolean.dimensional(spaced))
        parity = "".join("1" if (i).bit_count() % 2 else "0" for i in range(64))
        assert len(boolean.dimensional(parity)) < 10_000

    def test_a_pair_of_entries_shares_a_cell_from_n7(self) -> None:
        """Random tables pack two entries a cell and execute; or keeps its loop."""
        language = esolangs.Language("Dimensional")
        for witness in construction_boundaries("Dimensional")[
            "painted_to_packed_lookup"
        ]:
            n, table = witness.arity, witness.table()
            artifact = language.generate(table)
            assert ("[->4+<4[->5+<5[->4-<4]]]" in artifact.source) == (n == 7)
            restored = language.load_program(language.dump_program(artifact))
            prepared = language.prepare(restored)
            for row in range(0, len(table), 5):
                result = prepared.evaluate(row_bits(row, n))
                assert result.bit == table[row]
                assert result.observation.input_position == 2 * n - 1
        either = "0" + "1" * 127
        assert "[->4+<4[->5" not in esolangs.generate("Dimensional", either).source

    def test_a_sparse_table_with_trailing_zeros_executes(self) -> None:
        """Trailing zeros are painted like any other run; every row answers."""
        table = "0" * 9 + "1" + "0" * 6
        program = esolangs.generate("Dimensional", table).source
        for row, expected in enumerate(table):
            stdin = "\n".join(format(row, "04b"))
            assert (
                run(
                    "Dimensional",
                    program,
                    stdin=stdin,
                    limits=esolangs.ExecutionLimits(max_steps=10_000),
                ).output
                == expected
            )

    def test_scales_beyond_the_old_reference_cap(self) -> None:
        """The v3.0 interpreter's unbounded cells lift the old n <= 12 cap."""
        program = boolean.dimensional("0" * 4095 + "1")
        got = run_dimensional(program, ["1"] * 12)
        assert got == "1"


@pytest.mark.parametrize(
    ("program", "token"),
    [
        ("+=30.", "=30"),
        ("+:x.", ":x"),
        ("+>~3.", ">~3"),
        ("+!12.", "!12"),
        ("+?7.", "?7"),
        ("+$4.", "$4"),
        ("+{2}.", "{2"),
    ],
)
def test_dimensional_keeps_every_operand_with_its_command(
    program: str, token: str
) -> None:
    """A break inside any of these changes what the program does."""
    assert token in wrap_program(program, "dimensional", 1).split("\n")


@pytest.mark.medium
@pytest.mark.parametrize("kind", ["parity", "sparse"])
def test_fourteen_input_lookup_stays_within_step_cap(kind: str) -> None:
    n = 14
    size = 1 << n
    table = (
        "".join(str(row.bit_count() & 1) for row in range(size))
        if kind == "parity"
        else "0" * (size - 1) + "1"
    )
    program = dimensional(table)
    for row in (0, size // 3, size - 1):
        io = ScriptedIO("\n".join(format(row, f"0{n}b")) + "\n")
        machine = _Machine(program, io)
        for _ in range(200_000):
            if machine.halted:
                break
            machine.step()
        assert machine.halted
        assert (io.getvalue(), io.reads) == (table[row], n)


def _check_constants() -> None:
    for n, bit, options, program in constant_programs("Dimensional", range(1, 13)):
        if not options:
            assert len(program) == n + 3
        if options == {"width": 1}:
            assert max(map(len, program.splitlines())) == (1 if n <= 2 else 2)
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            stdin = esolangs.encode_inputs(
                "Dimensional", list(map(int, f"{row:0{n}b}"))
            )
            io = ReadFirstIO(stdin + "\n7\n", expected=n)
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            steps = count_steps(machine, 1999, written=written)
            assert io.getvalue() == bit
            assert io.past_end == 0
            assert io.input_num() == 7
            if not options:
                assert steps == n + 2
            assert (
                written.bits == 6 + len(program).bit_length() + (2 * n - 1).bit_length()
            )


def _check_first_essential_read() -> None:
    """Ignored prefixes preserve zero coordinates before the first indexed read."""
    for selected in ((0, 1, 6), (2, 4, 6), (0, 3, 5)):
        table = "".join(
            "00110110"[
                sum(
                    ((row >> (6 - position)) & 1) << (2 - bit)
                    for bit, position in enumerate(selected)
                )
            ]
            for row in range(128)
        )
        programs = [
            esolangs.generate("Dimensional", table).source,
            esolangs.generate("Dimensional", table, width=1).source,
            esolangs.generate("Dimensional", table, balance=True).source,
        ]
        weights, projected = input_weights(table, 7)
        if (packed := _packed(projected, weights)) is not None:
            programs.append(packed)
        for program in programs:
            for row in (0, 1, 21, 63, 127):
                io = ReadFirstIO(" ".join(f"{row:07b}") + " 7", expected=7)
                machine = _Machine(program, io)
                for _ in range(10_000):
                    if machine.halted:
                        break
                    machine.step()
                assert machine.halted
                assert io.getvalue() == table[row]
                assert io.reads == 7
                assert io.past_end == 0
                assert io.input_num() == 7
