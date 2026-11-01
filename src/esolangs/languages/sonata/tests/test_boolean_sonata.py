"""Tests for the Sonata Boolean generator."""

import pytest

import esolangs

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
    n = len(table).bit_length() - 1
    program = esolangs.generate("Sonata", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Sonata", bits)
        got = esolangs.run("Sonata", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Sonata", got) == table[row], (table, row)


def test_pair_table_prints_its_answer() -> None:
    """Seven essential bits store a char per row pair (all four symbols)."""
    table = "".join(f"{(r * 2654435761) >> 7 & 1}" for r in range(128))
    program = esolangs.generate("Sonata", table)
    assert "@#b_T0->=1" in program
    for row in range(128):
        bits = [(row >> (6 - i)) & 1 for i in range(7)]
        stdin = esolangs.encode_inputs("Sonata", bits)
        got = esolangs.run("Sonata", program, stdin=stdin, timeout=5)
        assert esolangs.read_answer("Sonata", got) == table[row], row


def _check_constants() -> None:
    from esolangs.languages.sonata.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Sonata", bit * (1 << n), **options)
                assert len(program) == (16 if n == 2 else 2 * n + 5)
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    io = ScriptedIO(f"{row:0{n}b}")
                    machine = _Machine(program, io)
                    written = WrittenState(machine.snapshot())
                    for _ in range(2):
                        machine.step()
                        written.sample(machine.snapshot())
                    assert machine.halted
                    assert io.getvalue() == "=" + bit
                    assert written.bits == 8 * max(n, 2) + 2
                invalid = "0" * (n + 1)
                assert esolangs.run("Sonata", program, stdin=invalid) == invalid
    assert (
        sum(len(esolangs.generate("Sonata", f"{v:08b}")) for v in range(256)) == 30314
    )
