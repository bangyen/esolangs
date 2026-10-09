"""Check the signed-ball code, traveling stride, and executed rank decoder."""

import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.brainfuck import _Machine
from esolangs.interpreters.tape_based.factor import run
from tests.proofs._factor_blocks import (
    ball_count,
    block_decoder,
    block_program,
    rank,
    unrank,
)
from tests.proofs._factor_counter import _counter
from tests.proofs.test_factor_print import _render


def test_ball_codec() -> None:
    for cells in range(5):
        for budget in range(5):
            count = ball_count(cells, budget)
            vectors = [unrank(value, cells, budget) for value in range(count)]
            assert len({tuple(vector) for vector in vectors}) == count
            for value, vector in enumerate(vectors):
                assert len(vector) == cells
                assert sum(map(abs, vector)) <= budget
                assert rank(vector, budget) == value
    with pytest.raises(ValueError, match="exceeds"):
        unrank(ball_count(14, 14))


def test_ball_capacity_and_source_bound() -> None:
    assert ball_count(14, 14) == 7_923_848_253 > 2**32
    for cells in range(1, 15):
        for budget in range(1, 15):
            assert ball_count(cells, budget) == (
                ball_count(cells - 1, budget)
                + ball_count(cells, budget - 1)
                + ball_count(cells - 1, budget - 1)
            )
    rng = random.Random(927)
    decoder_length = len(block_decoder())
    assert decoder_length == 147_967
    for n in range(5, 13):
        table = "".join(rng.choice("01") for _ in range(2**n))
        vectors = [unrank(int(table[i : i + 32], 2)) for i in range(0, len(table), 32)]
        for i, vector in enumerate(vectors):
            assert rank(vector) == int(table[32 * i : 32 * (i + 1)], 2)
            assert sum(map(abs, vector)) <= 14
        width = n - 5
        counter_length = 180 * width**2 + 1033 * width + 119 if width else 0
        assert len(_counter(width, stride=15)) == counter_length
        emitted = block_program(table)
        assert len(emitted) == (
            15 * len(vectors)
            + 13
            + sum(sum(map(abs, vector)) for vector in vectors)
            + counter_length
            + 1
            + decoder_length
        )
        assert len(emitted) <= 29 * len(table) / 32 + counter_length + 147_981


@pytest.mark.medium
@pytest.mark.parametrize("width", range(4))
def test_block_stride_preserves_payloads(width: int) -> None:
    blocks = 2**width
    payloads = [(i % 5) - 2 for i in range(14 * blocks)]
    data = (
        ">".join(
            "".join(
                ">" + ("+" if v >= 0 else "-") * abs(v)
                for v in payloads[14 * i : 14 * (i + 1)]
            )
            for i in range(blocks)
        )
        + "<" * 14
    )
    code = data + _counter(width, stride=15)
    for row in range(blocks):
        bits = format(row, f"0{width}b") if width else ""
        machine = _Machine(code, ScriptedIO("".join(bits)))
        while not machine.halted:
            assert machine.ptr or code[machine.ind] != "<"
            machine.step()
        assert machine.ptr == 15 * row
        assert machine.input_position() == width
        assert not any(machine.tape[::15])
        assert tuple(
            machine.tape[15 * block + offset + 1]
            for block in range(blocks)
            for offset in range(14)
        ) == tuple(v % 256 for v in payloads)


@pytest.mark.slow
def test_block_factor_executes() -> None:
    table = format(0xA596B47C, "032b")
    program = _render(block_program(table))
    io = ScriptedIO("00000")
    run(program, io)
    assert io.getvalue() == table[0] == "1"
