"""Tests for the 1 + i Boolean generator."""

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_constant_output

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
        _check_arithmetic_tails()
    n = len(table).bit_length() - 1
    program = esolangs.generate("1 + i", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("1 + i", bits)
        got = esolangs.run("1 + i", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("1 + i", got) == table[row], (table, row)


def _check_constants() -> None:
    import esolangs
    from esolangs.languages.one_i.interpreter import run

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("1 + i", bit * (1 << n), **options)
                for row in ("0" * n, "1" * n):
                    io = ReadFirstIO(
                        esolangs.encode_inputs("1 + i", [int(b) for b in row]) + "7\n",
                        expected=n,
                    )
                    assert_constant_output(run, program, io, bit, n)
                    assert io.input_num() == 7


def _check_arithmetic_tails() -> None:
    from fractions import Fraction

    from esolangs.languages.one_i.interpreter import _Fn, _Machine
    from esolangs.languages.one_i.proof_formulas import execution, workspace
    from esolangs.languages.one_i.tests.formulas import workspace_witness
    from scripts.benchmark import WrittenState

    tables = [f"{v:04b}" for v in range(16)]
    tables += [
        "".join(str(row.bit_count() % 2) for row in range(1 << n)) for n in (3, 7, 8)
    ]
    tables += [
        "".join(str((row & mask).bit_count() % 2) for row in range(1 << n))
        for n, mask in ((6, 32), (8, 129))
    ]
    tables += [
        "".join(
            str(int(bool(row & a) and (bool(row & b) != invert)))
            for row in range(1 << n)
        )
        for n, a, b, invert in ((4, 8, 2, False), (5, 16, 2, True))
    ]
    tables += [workspace_witness(n) for n in range(2, 10)]
    for table in tables:
        n = len(table).bit_length() - 1
        program = esolangs.generate("1 + i", table)
        for row in (0, (1 << n) // 3, 1 << (n - 1), (1 << n) - 1):
            io = ReadFirstIO(
                esolangs.encode_inputs("1 + i", list(map(int, f"{row:0{n}b}"))) + "7\n",
                expected=n,
            )
            machine = _Machine(program, io)
            written = WrittenState(machine.snapshot())
            steps = 0
            while not machine.halted:
                machine.step()
                written.sample(machine.snapshot())
                steps += 1
                for value in machine.values:
                    assert isinstance(value, _Fn) or (
                        isinstance(value, tuple)
                        and all(isinstance(part, Fraction) for part in value)
                    )
            assert io.getvalue() == table[row]
            assert io.past_end == 0
            assert io.input_num() == 7
            assert steps <= execution(n, program)
            assert written.bits <= workspace(n, program)
