"""qoibl generator tests."""

import random

import pytest

import esolangs
from esolangs.generation.wrap import balance_score
from esolangs.languages.qoibl import generator as boolean
from esolangs.languages.qoibl.generator import _horner_lines, _source
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.generators.boolean_runners import _runner
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import (
    assert_an_ignored_input_costs,
    assert_parity_at_most_doubles,
    three_input_corpus_size,
)
from tests.support.witness_tables import witnesses

run_qoibl = _runner("qoibl", lines=True)


class TestQoibl:
    @pytest.mark.parametrize("width", [1, 3, 80])
    def test_narrow_horner_literals_execute_small_tables(self, width: int) -> None:
        from esolangs.languages.qoibl.interpreter import _Machine
        from scripts.docs.resource_evidence import resource_bounds

        bounds = resource_bounds("Qoibl")
        execution = bounds["execution"].formula
        workspace = bounds["workspace"].formula

        for n in (1, 2, 3):
            for table in witnesses(n):
                program = esolangs.generate("Qoibl", table, width=width).source
                assert max(map(len, program.splitlines())) <= max(width, 2)
                for row in range(1 << n):
                    io = ScriptedIO(f"{row:0{n}b}Q")
                    machine = _Machine(program, io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.workspace_snapshot())
                        steps += 1
                    assert io.getvalue() == table[row]
                    assert io.reads == n
                    assert io.past_end == 0
                    assert io.input_char() == ord("Q")
                    assert steps == execution(n, program)
                    assert written.bits <= workspace(n, program)

    @pytest.mark.medium
    @pytest.mark.parametrize(
        ("n", "width"), [(5, 3), (5, 13), pytest.param(8, 1, marks=pytest.mark.slow)]
    )
    def test_narrow_horner_larger_literals(self, n: int, width: int) -> None:
        rng = random.Random(20260930 + n)
        for table in (
            "".join(str(row.bit_count() & 1) for row in range(2**n)),
            format(rng.getrandbits(2**n), f"0{2**n}b"),
        ):
            program = boolean.qoibl(table, width)
            for row in rng.sample(range(2**n), 4):
                assert run_qoibl(program, list(format(row, f"0{n}b"))) == table[row]

    def test_narrow_horner_floor_and_corpus_size(self) -> None:
        assert max(map(len, boolean.qoibl("0110", 1).splitlines())) == 2
        assert (
            sum(len(boolean.qoibl(format(v, "08b"), 1)) for v in range(256)) == 405458
        )

    def test_the_table_is_one_literal(self) -> None:
        """The whole table rides in a single binary literal, bit k for row k."""
        program = boolean.qoibl("00100000")
        # 0b100: row 2 is the only one set, and it is bit 2 (its
        # complement packs no shorter, and reversed it packs longer).
        from esolangs.languages.qoibl.interpreter import tokenize

        assert sum(tokens.count("yee") for tokens in tokenize(program)) == 1
        assert program.endswith("tt")

    def test_the_reads_are_one_statement_each(self) -> None:
        """Only the input count scales the statements; the table does not."""
        from esolangs.languages.qoibl.interpreter import tokenize

        counts = [
            len(
                tokenize(
                    boolean.qoibl(
                        "".join(str(row.bit_count() & 1) for row in range(2**n))
                    )
                )
            )
            for n in range(1, 6)
        ]
        assert counts == [7, 8, 9, 10, 11]

    def test_a_constant_table_still_reads_its_inputs(self) -> None:
        """A constant function packs to zero but keeps the reads it owes."""
        program = boolean.qoibl("0000")
        from esolangs.languages.qoibl.interpreter import tokenize

        assert sum(tokens.count("et") for tokens in tokenize(program)) == 2
        assert program == "weeweetweweeweetwettyyeeeett"


def test_constant_table_reads_cost_one_line_each() -> None:
    """Past the first read a constant's inputs are ignored reads, not Horner steps."""
    for bit in "01":
        sizes = [len(boolean.qoibl(bit * 2**n)) for n in (4, 6, 8)]
        assert sizes[2] - sizes[1] == sizes[1] - sizes[0] < 80 * 2
        for n in (1, 3, 5):
            program = boolean.qoibl(bit * 2**n)
            for row in (0, 2**n - 1):
                assert run_qoibl(program, list(f"{row:0{n}b}")) == bit


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """One read into a register the next write clears."""
    assert_analysis_complement("Qoibl", "input_weights")
    assert_an_ignored_input_costs("Qoibl", 6, 13)
    _check_compact_input_tokens()


@pytest.mark.medium
def test_parity_source_at_most_doubles_per_input() -> None:
    assert_parity_at_most_doubles(boolean.qoibl, range(7, 11), 800)


@pytest.mark.parametrize("seed", range(6))
def test_balance_stays_within_five_percent_of_the_retired_sweep(seed: int) -> None:
    from esolangs.languages.qoibl.tests.balance_oracle import sweep_balance_qoibl

    rng = random.Random(seed)
    for inputs in range(1, 8):
        table = format(rng.getrandbits(1 << inputs), f"0{1 << inputs}b")
        default = esolangs.generate("Qoibl", table).source
        balanced = esolangs.generate("Qoibl", table, balance=True).source
        oracle = sweep_balance_qoibl(table, default)
        assert balance_score(balanced)[0] <= 1.05 * balance_score(oracle)[0]
        for row in (0, (1 << inputs) - 1, rng.randrange(1 << inputs)):
            bits = list(format(row, f"0{inputs}b"))
            assert run_qoibl(balanced, bits) == table[row]


class TestQoiblSweepPins:
    """Pins from the mutation sweep: the Horner scratch variable and the
    closed-form balance widths were unobserved."""

    def test_the_horner_scratch_is_variable_two(self) -> None:
        # _horner_lines expands over-long literals into variable 2 ("ye");
        # variable 3 computes the same programs but is not the scratch.
        lines = [f"we y we {'y' * 27} we"]
        expanded = _horner_lines(lines, 4)
        assert expanded[0].startswith("we ye we ")
        assert any("qe ye qe" in line for line in expanded)
        program = boolean.qoibl("0001")
        assert boolean._fit(program, None) == program
        for row, answer in enumerate("0001"):
            assert run_qoibl(program, list(f"{row:02b}")) == answer

    @pytest.mark.parametrize(
        ("table", "shape"),
        [
            ("00000000", (54, 5, 11)),
            ("0000000000000000", (68, 6, 12)),
            (
                "0110000101111110000011100110010100101011000101100000100001111110101010110100111010111101001001001011011010000100010001000100000011001101000110010000110110011110011110001010001001101011011100100101110101000111100010101011000110110001010001100111100010110001",
                (1300, 27, 56),
            ),
        ],
    )
    def test_balanced_shapes_are_pinned(self, table: str, shape: tuple) -> None:
        program = str(esolangs.generate("Qoibl", table, balance=True).source)
        assert (
            len(program),
            program.count("\n") + 1,
            max(map(len, program.split("\n"))),
        ) == shape


def test_constant_audit_read_first_and_sentinel() -> None:
    from esolangs.languages.qoibl.interpreter import _Machine

    for n in range(1, 13):
        rows = range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1)
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Qoibl", bit * (1 << n), **options).source
                if not options:
                    assert len(program) == 9 * n + 10
                for row in rows:
                    io = ReadFirstIO(
                        esolangs.encode_inputs(
                            "Qoibl", list(map(int, format(row, f"0{n}b")))
                        )
                        + "Q",
                        expected=n,
                    )
                    machine = _Machine(program, io)
                    steps = 0
                    while not machine.halted and steps < 1000:
                        machine.step()
                        steps += 1
                    assert machine.halted
                    if not options:
                        assert steps == n + 1
                    assert io.getvalue() == bit
                    assert io.reads == n
                    assert io.input_char() == ord("Q")


def test_constant_audit_three_input_corpus_size() -> None:
    assert three_input_corpus_size("Qoibl") == 51216


def _check_compact_input_tokens() -> None:
    """Compaction preserves statements, all ordered reads and their answers."""
    from esolangs.languages.qoibl.interpreter import _Machine, tokenize
    from scripts.docs.resource_evidence import resource_bounds

    bounds = resource_bounds("Qoibl")
    execution = bounds["execution"].formula
    workspace = bounds["workspace"].formula

    cases = [(3, f"{value:08b}", None) for value in range(256)]
    parity = "".join(str(row.bit_count() & 1) for row in range(1 << 10))
    cases += [(10, parity, None), (10, parity, 80)]
    for n, table, width in cases:
        program = boolean.qoibl(table, width)
        if width is None:
            assert tokenize(program) == tokenize(_source(table))
        rows = range(8) if n == 3 else (0, (1 << n) - 1)
        for row in rows:
            io = ScriptedIO(f"{row:0{n}b}Q")
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            steps = 0
            while not machine.halted:
                machine.step()
                written.sample(machine.workspace_snapshot())
                steps += 1
                if io.getvalue():
                    assert io.reads == n
            assert io.getvalue() == table[row]
            assert io.reads == n
            assert io.input_char() == ord("Q")
            assert steps == execution(n, program)
            assert written.bits <= workspace(n, program)
