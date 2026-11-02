"""Tests for the Kiss Boolean generator."""

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
    program = esolangs.generate("Kiss", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Kiss", bits)
        got = esolangs.run("Kiss", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Kiss", got) == table[row], (table, row)


def _check_constants() -> None:
    from esolangs.languages.kiss.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

    for n in range(1, 13):

        class ReadFirstIO(ScriptedIO):
            expected = n

            def _write(self, value):
                assert self.reads == self.expected
                super()._write(value)

        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Kiss", bit * (1 << n), **options)
                if not options:
                    assert len(program) == 9 * n
                peak_steps = 0
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "Kiss", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "7")
                    machine = _Machine(program, io)
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        steps += 1
                        assert steps < 1000
                    assert io.getvalue().strip() == bit
                    assert io.past_end == 0
                    assert io.input_char() == ord("7")
                    if not options:
                        assert steps <= 4 * n - 1
                        peak_steps = max(peak_steps, steps)
                if not options:
                    assert peak_steps == 4 * n - 1
