"""Tests for the Aprknia Boolean generator."""

import pytest

import esolangs

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
    from esolangs.languages.aprknia.interpreter import run
    from esolangs.runtime.io import ScriptedIO

    n = len(table).bit_length() - 1

    class ReadFirstIO(ScriptedIO):
        def _write(self, value: object) -> None:
            assert self.reads == n
            super()._write(value)

    program = esolangs.generate("Aprknia", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Aprknia", bits)
        io = ReadFirstIO(stdin + "7")
        run(program, io)
        got = io.getvalue()
        assert io.past_end == 0
        assert io.input_char() == ord("7")
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Aprknia", got) == table[row], (table, row)


def _check_constants() -> None:
    import esolangs
    from esolangs.languages.aprknia.interpreter import run
    from esolangs.runtime.io import ScriptedIO

    for n in range(1, 13):

        class ReadFirstIO(ScriptedIO):
            expected = n

            def _write(self, value: object) -> None:
                assert self.reads == self.expected
                super()._write(value)

        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Aprknia", bit * (1 << n), **options)
                for row in ("0" * n, "1" * n):
                    io = ReadFirstIO(row + "7")
                    run(program, io)
                    assert io.getvalue() == bit
                    assert io.reads == n
                    assert io.past_end == 0
                    assert io.input_char() == ord("7")
