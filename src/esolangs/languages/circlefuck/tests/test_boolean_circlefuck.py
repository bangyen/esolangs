"""Circlefuck boolean generation: the deleting lookup and its index."""

import random

import pytest

import esolangs
from esolangs import run as execute
from esolangs.languages.circlefuck import generator as boolean
from esolangs.languages.circlefuck.generator import _DIGIT_BITS
from esolangs.runtime.io import ScriptedIO
from tests.generators.boolean_runners import _runner
from tests.support.analysis_support import assert_analysis_complement
from tests.support.evaluation import _evaluate
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import (
    assert_constant_output,
    constant_programs,
    measure_run,
)

run_circlefuck = _runner("circlefuck")


def _rows(program: str, table: str, n: int) -> None:
    for combo in range(2**n):
        bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
        got = run_circlefuck(program, bits)
        assert got == table[combo], f"inputs {bits}"


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_reads_into_spent_code_and_prints_a_literal_tail(n, bit) -> None:
    from esolangs.languages.circlefuck.interpreter import _Machine

    if n == 1 and bit == "0":
        _check_constants()
        _check_reader()
    table = bit * (1 << n)
    program = esolangs.generate("Circlefuck", table).source
    assert program == "," * n + "<.@" + bit
    assert len(program) == n + 4
    for options in ({}, {"width": 1}, {"width": 8}, {"width": 40}, {"balance": True}):
        wrapped = esolangs.generate("Circlefuck", table, **options).source
        assert _evaluate("Circlefuck", wrapped, inputs=n) == table
    for row in range(1 << n):
        io = ScriptedIO(format(row, f"0{n}b") + "0")
        machine = _Machine(program, io)
        for _ in range(n + 3):
            assert not machine.halted
            machine.step()
        assert machine.halted
        assert io.getvalue() == bit
        assert io.reads == n
        assert io.position() == n
        assert machine.ptr == n + 3
        assert len(machine.cells) == n + 4


class TestCirclefuck:
    def test_the_index_survives_more_than_one_digit(self) -> None:
        """Past 128 entries the index needs a carry, and it is spent right."""
        n = 9
        table = "".join("1" if row % 3 == 0 else "0" for row in range(2**n))
        program = boolean.circlefuck(table)
        assert program.count("+" * (1 << _DIGIT_BITS)) == 1  # one carry gadget
        for row in (0, 127, 128, 129, 255, 256, 257, 383, 384, 511):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_circlefuck(program, bits) == table[row], row

    @pytest.mark.parametrize("fed", ["", "1\n", "x\ny\nz\n", "9\n9\n9\n"])
    def test_a_byte_outside_the_alphabet_still_lands_in_the_table(
        self, fed: str
    ) -> None:
        """Whatever is read, the index stays inside the table."""
        from esolangs.languages.circlefuck.interpreter import run
        from tests.interpreters.runner import run_program

        table = "01101001"
        got = run_program(run, boolean.circlefuck(table), fed)
        assert got in set(table), got

    def test_the_table_is_one_character_an_entry(self) -> None:
        """Doubling the arity doubles the program's table and nothing else."""
        rng = random.Random(11)
        sizes = {}
        for n in (10, 11, 12):
            table = "".join(rng.choice("01") for _ in range(2**n))
            sizes[n] = len(boolean.circlefuck(table))
        grew = sizes[11] - sizes[10]
        assert abs(grew - 2**10) < 0.1 * 2**10, grew
        assert abs((sizes[12] - sizes[11]) - 2 * grew) < 0.1 * 2**10

    def test_an_inessential_input_is_read_but_not_tabulated(self) -> None:
        """A degenerate table is the smaller table it really is."""
        assert_analysis_complement("Circlefuck", "read_at")
        assert_analysis_complement(
            "Circlefuck", "symmetric_weights", "0110100110010110"
        )
        assert len(boolean.circlefuck("11111111")) < len(
            boolean.circlefuck("10101010"),
        )
        assert len(boolean.circlefuck("10101010")) < len(
            boolean.circlefuck("10010110"),
        )
        assert len(boolean.circlefuck("11110000")) < len(
            boolean.circlefuck("10010110"),
        )
        _rows(boolean.circlefuck("11111111"), "11111111", 3)
        _rows(boolean.circlefuck("11110000"), "11110000", 3)


def test_run_uses_native_eof() -> None:
    program = boolean.circlefuck("10")  # reads one input bit
    assert execute("Circlefuck", program, stdin="").output == "0"


def _check_constants() -> None:
    from esolangs.languages.circlefuck.interpreter import run

    for n, bit, _options, program in constant_programs("Circlefuck", range(1, 13)):
        for row in ("0" * n, "1" * n):
            io = ReadFirstIO(row + "7", expected=n)
            assert_constant_output(run, program, io, bit, n)
            assert io.input_char() == ord("7")


def _check_reader() -> None:
    from esolangs.languages.circlefuck.interpreter import run

    total = 0
    for value in range(256):
        table = f"{value:08b}"
        program = str(esolangs.generate("Circlefuck", table).source)
        total += len(program)
        for row in range(8):
            io = ReadFirstIO(f"{row:03b}" + "7", expected=3)
            run(program, io)
            assert io.getvalue() == table[row]
            assert io.past_end == 0
            assert io.input_char() == ord("7")
    assert total == 34090

    from esolangs.languages.circlefuck.interpreter import _Machine
    from esolangs.languages.circlefuck.proof_formulas import workspace
    from scripts.docs.resource_evidence import resource_bounds

    execution = resource_bounds("Circlefuck")["execution"].formula

    table = "00110110"
    for options in ({}, {"width": 1}, {"balance": True}):
        program = str(esolangs.generate("Circlefuck", table, **options).source)
        io = ReadFirstIO("1117", expected=3)
        machine = _Machine(program, io)
        steps, written = measure_run(machine)
        assert steps == execution(3, program)
        assert written.bits == workspace(3, program)
        assert io.getvalue() == table[7]
        assert io.input_char() == ord("7")
