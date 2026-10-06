"""Execute Factor's traveling counter and pin its tape and source invariants."""

import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.brainfuck import _Machine
from esolangs.interpreters.tape_based.brainfuck import run as run_bf
from tests.proofs._factor_counter import _counter, _decoder, counter_program


@pytest.mark.parametrize("width", range(6))
def test_counter_preserves_payloads(width: int) -> None:
    pairs = 2**width
    payloads = [(i % 3) - 1 for i in range(pairs)]
    data = (
        ">"
        + ">>".join(("+" if value >= 0 else "-") * abs(value) for value in payloads)
        + "<"
    )
    code = data + _counter(width)
    # The first and last rows: the counter's two ends.
    for row in sorted({0, pairs - 1}):
        bits = format(row, f"0{width}b") if width else ""
        machine = _Machine(code, ScriptedIO("".join(bits)))
        while not machine.halted:
            assert machine.ptr or code[machine.ind] != "<"
            machine.step()
        assert machine.ptr == 2 * row
        assert machine.input_position() == width
        assert not any(machine.tape[::2])
        assert machine.tape[1 : 2 * pairs : 2] == tuple(v % 256 for v in payloads)


@pytest.mark.medium
def test_phase_decoder_executes() -> None:
    for phase in range(4):
        for pair in range(4):
            rotated = (pair + phase) % 4
            value = -1 if rotated == 3 else rotated
            code = ("+" if value >= 0 else "-") * abs(value) + _decoder(phase)
            for bit in range(2):
                io = ScriptedIO(str(bit))
                run_bf(code, io)
                assert io.getvalue() == str((pair >> (1 - bit)) & 1)


def test_counter_character_bound() -> None:
    rng = random.Random(926)
    assert not _counter(0)
    assert [len(_decoder(p)) for p in range(4)] == [290, 289, 288, 287]
    for n in range(1, 13):
        width = n - 1
        overhead = 24 * width**2 + 227 * width + 28 if width else 0
        assert len(_counter(width)) == overhead
        length = 2**n
        tables = ["0" * length, "1" * length] + [
            "".join(rng.choice("01") for _ in range(length)) for _ in range(8)
        ]
        for table in tables:
            values = [int(table[i : i + 2], 2) for i in range(0, length, 2)]
            costs = [
                sum(min((v + p) % 4, 4 - (v + p) % 4) for v in values) for p in range(4)
            ]
            phase = min(range(4), key=costs.__getitem__)
            assert sum(costs) == 4 * len(values)
            assert costs[phase] <= len(values)
            assert (
                len(counter_program(table))
                == length + costs[phase] + overhead + 291 - phase
            )
            assert (
                len(counter_program(table))
                <= 3 * length / 2 + 24 * n**2 + 179 * n + 116
            )
