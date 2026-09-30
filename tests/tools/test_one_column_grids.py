"""One-column layouts execute through the public input and answer interfaces."""

import random

import pytest

import esolangs


@pytest.mark.parametrize("language", ["Befunge", "Fish", "Super SNUSP", "thisthat"])
@pytest.mark.medium
def test_small_tables_and_fitting_layouts(language: str) -> None:
    for n in range(1, 4):
        count = 1 << n
        for value in range(1 << count):
            table = f"{value:0{count}b}"
            raw = esolangs.generate(language, table)
            natural = max(map(len, raw.splitlines()))
            assert esolangs.generate(language, table, natural) == raw
            program = esolangs.generate(language, table, 1)
            for row, expected in enumerate(table):
                bits = [int(bit) for bit in f"{row:0{n}b}"]
                output = esolangs.run(
                    language, program, stdin=esolangs.encode_inputs(language, bits)
                )
                assert esolangs.read_answer(language, output) == expected


@pytest.mark.parametrize("language", ["Befunge", "Fish", "Super SNUSP"])
@pytest.mark.parametrize("bias", [0, 1])
@pytest.mark.parametrize("n", [4, 6, 10])
def test_vertical_parity_reads_every_input(language: str, bias: int, n: int) -> None:
    table = "".join(str((row.bit_count() & 1) ^ bias) for row in range(1 << n))
    program = esolangs.generate(language, table, 1)
    assert max(map(len, program.splitlines())) == 1
    if language == "Befunge":
        assert len(program.splitlines()) <= 25
    for row in (0, 1, 3, min(27, (1 << n) - 1), (1 << n) - 1):
        bits = [int(bit) for bit in f"{row:0{n}b}"]
        output = esolangs.run(
            language, program, stdin=esolangs.encode_inputs(language, bits)
        )
        assert esolangs.read_answer(language, output) == table[row]


@pytest.mark.parametrize("language", ["Befunge", "Fish", "Super SNUSP", "thisthat"])
def test_xor_has_one_column(language: str) -> None:
    assert max(map(len, esolangs.generate(language, "0110", 1).splitlines())) == 1


@pytest.mark.parametrize("language", ["Befunge", "Fish", "Super SNUSP", "thisthat"])
def test_larger_sampled_tables(language: str) -> None:
    rng = random.Random(104)
    for n in (4, 5, 6):
        table = "".join(str(rng.randrange(2)) for _ in range(1 << n))
        program = esolangs.generate(language, table, 1)
        for row in (0, 1, 3, 11, (1 << n) - 1):
            bits = [int(bit) for bit in f"{row:0{n}b}"]
            output = esolangs.run(
                language, program, stdin=esolangs.encode_inputs(language, bits)
            )
            assert esolangs.read_answer(language, output) == table[row]
