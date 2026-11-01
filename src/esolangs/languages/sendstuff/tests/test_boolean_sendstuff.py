"""Tests for the SendStuff Boolean generator."""

import pytest

import esolangs
from esolangs.languages.sendstuff.generator import sendstuff

#: Nonconstant one- and two-input tables; a diagram's sharing bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(1, 2**2**n - 1)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("SendStuff", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("SendStuff", bits)
        got = esolangs.run("SendStuff", program, stdin=stdin, timeout=5)
        assert esolangs.read_answer("SendStuff", got) == table[row], (table, row)


def test_equal_subtables_share_one_node() -> None:
    # Parity: one node per (level, parity), not one per row prefix.
    assert sendstuff("0110100110010110").count("!y ") == 7


@pytest.mark.medium
def test_constants_read_first_within_bounds_and_keep_a_sentinel() -> None:
    from esolangs.languages.sendstuff.interpreter import _Machine
    from esolangs.languages.sendstuff.proof_formulas import workspace
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
                program = esolangs.generate("SendStuff", bit * (1 << n), **options)
                if not options and n == 8:
                    assert len(program) == 87
                rows = range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1)
                for row in rows:
                    stdin = esolangs.encode_inputs(
                        "SendStuff", list(map(int, format(row, f"0{n}b")))
                    )
                    io = ReadFirstIO(stdin + "Q")
                    machine = _Machine(program, io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted and steps <= n + 2:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                    assert machine.halted
                    assert io.getvalue() == bit
                    assert steps == n + 2
                    assert written.bits <= workspace(n, program)
                    assert io.input_char() == ord("Q")
    assert (
        sum(len(esolangs.generate("SendStuff", format(v, "08b"))) for v in range(256))
        == 49336
    )
