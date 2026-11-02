"""Tests for the Shakespeare Boolean generator."""

import random

import pytest

import esolangs

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


def _wrong_rows(table: str, program: str) -> int:
    n = len(table).bit_length() - 1
    from esolangs.languages.shakespeare.interpreter import run
    from esolangs.runtime.io import ScriptedIO

    class ReadFirstIO(ScriptedIO):
        def _write(self, value: object) -> None:
            assert self.reads == n
            super()._write(value)

    wrong = 0
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Shakespeare", bits)
        io = ReadFirstIO(stdin + "Q")
        run(program, io)
        got = io.getvalue()
        assert io.past_end == 0
        assert io.input_token() == "Q"
        wrong += esolangs.read_answer("Shakespeare", got) != table[row]
    return wrong


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    assert _wrong_rows(table, esolangs.generate("Shakespeare", table)) == 0
    if table == "00":
        assert (
            sum(len(esolangs.generate("Shakespeare", f"{v:08b}")) for v in range(256))
            == 215909
        )


@pytest.mark.parametrize("n", [5, 6])
def test_random_tables_past_the_chunk_width_compute_their_rows(n: int) -> None:
    """A 64-row table packs in one sentence; 128 and up need several."""
    rng = random.Random(n)
    for table in (format(rng.getrandbits(2**n), f"0{2**n}b"), "01" * 2 ** (n - 1)):
        assert _wrong_rows(table, esolangs.generate("Shakespeare", table)) == 0

    if n == 6:
        _check_large_packing_bounds()


def _check_large_packing_bounds() -> None:
    from esolangs.languages.shakespeare.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    # All inputs matter; the sparse signed form still crosses sixteen chunks.
    table = "0" * 513 + "1" * 511
    program = esolangs.generate("Shakespeare", table)
    io = ScriptedIO("1\n" * 10)
    machine = _Machine(program, io)
    written = WrittenState(machine.snapshot())
    steps = 0
    while not machine.halted:
        machine.step()
        written.sample(machine.snapshot())
        steps += 1
        assert steps <= 42
    assert steps == 42
    assert written.bits == 2063
    assert io.getvalue() == "1"


def test_a_flipped_bit_is_caught() -> None:
    """Positive control: a program built for another table fails some row."""
    table = "01101001"
    flipped = "01101011"
    assert _wrong_rows(flipped, esolangs.generate("Shakespeare", table)) > 0


def test_the_majority_polarity_packs_the_complement() -> None:
    """OR has one zero: its complement is the number 1, not 255 set bits."""
    from esolangs.languages.shakespeare.generator import _program

    assert len(esolangs.generate("Shakespeare", "01111111")) < len(
        _program("01111111", 3, [0, 1, 2], invert=False)
    )


def test_constant_audit_read_first_and_sentinel() -> None:
    from esolangs.languages.shakespeare.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

    for n in range(1, 13):

        class ReadFirstIO(ScriptedIO):
            expected = n

            def _write(self, value):
                assert self.reads == self.expected
                super()._write(value)

        rows = range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1)
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Shakespeare", bit * (1 << n), **options)
                if not options:
                    assert len(program) == 29 * n + 155 - 4 * int(bit)
                for row in rows:
                    io = ReadFirstIO(
                        esolangs.encode_inputs(
                            "Shakespeare", list(map(int, format(row, f"0{n}b")))
                        )
                        + "Q"
                    )
                    machine = _Machine(program, io)
                    steps = 0
                    while not machine.halted and steps <= n + 3:
                        machine.step()
                        steps += 1
                    assert machine.halted
                    assert io.getvalue() == bit
                    assert io.reads == n
                    assert io.input_char() == ord("\n")
                    assert io.input_char() == ord("Q")
