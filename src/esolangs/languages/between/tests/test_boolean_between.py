"""Tests for the Between Boolean generator."""

import pytest

import esolangs

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("Between", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Between", bits)
        got = esolangs.run("Between", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Between", got) == table[row], (table, row)


def test_ignored_inputs_are_read_but_never_tested() -> None:
    """An ignored input reads into the scratch variable; no line tests it."""
    program = esolangs.generate("Between", "00110011")  # depends on input 1 only
    assert program.count("]i.") == 3
    assert program.count("f([") == 1


def test_constant_table_reads_every_input() -> None:
    _check_constants()
    program = esolangs.generate("Between", "1111")
    assert program.count("]i.") == 2
    assert "f(" not in program


def test_equal_subtables_are_one_block() -> None:
    """A repeated subtable is placed once and branched to."""
    once = esolangs.generate("Between", "01100110")
    assert once.count("p.") == 2


def _check_constants() -> None:
    from esolangs.languages.between.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    for n in range(1, 13):

        class ReadFirstIO(ScriptedIO):
            expected = n

            def _write(self, value):
                assert self.reads == self.expected
                super()._write(value)

        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Between", bit * (1 << n), **options)
                if not options:
                    assert len(program) == 6 * n + 11
                peak = 0
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "Between", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "7\n")
                    machine = _Machine(program, io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                        assert steps <= n + 2
                    assert io.getvalue() == bit
                    assert io.past_end == 0
                    assert io.input_str() == "7"
                    assert steps == n + 2
                    assert (
                        written.bits <= 16 + (n + 2).bit_length() + (2 * n).bit_length()
                    )
                    peak = max(peak, written.bits)
                assert peak == 16 + (n + 2).bit_length() + (2 * n).bit_length()
