"""Execute Factor's literal tape walk and pin its address and source bounds."""

import itertools
import random
from collections.abc import Callable

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.brainfuck import _Machine
from esolangs.interpreters.tape_based.factor import run
from tests.proofs._factor_walk import packed_program, walked_program
from tests.proofs.test_factor_print import _render


@pytest.mark.medium
@pytest.mark.parametrize("n", range(1, 7))
@pytest.mark.parametrize("partition", range(2))
@pytest.mark.parametrize("witness", [walked_program, packed_program])
def test_walked_witness_executes(
    n: int, partition: int, witness: Callable[[str], str]
) -> None:
    rng = random.Random(922 + n)
    tables = (
        [format(i, f"0{2**n}b") for i in range(2 ** (2**n))]
        if n <= 3
        else [
            "0" * 2**n,
            "1" * 2**n,
            "".join(str(i.bit_count() % 2) for i in range(2**n)),
        ]
        + ["".join(rng.choice("01") for _ in range(2**n)) for _ in range(8)]
    )
    for table in tables[partition::2]:
        program = _render(witness(table))
        for bits in itertools.product("01", repeat=n):
            io = ScriptedIO("".join(bits))
            run(program, io)
            assert io.getvalue() == table[int("".join(bits), 2)]


@pytest.mark.medium
@pytest.mark.parametrize("n", range(1, 7))
def test_walk_lands_on_every_address(n: int) -> None:
    code = walked_program("0" * 2**n)
    for row in range(2**n):
        io = ScriptedIO("".join(format(row, f"0{n}b")))
        machine = _Machine(code, io)
        while not machine.halted:
            machine.step()
        assert machine.ptr == 2 * row + 1
        assert machine.input_position() == n
        assert not any(machine.tape[::2])
        assert io.getvalue() == "0"


def test_walk_character_bound() -> None:
    rng = random.Random(923)
    for n in range(1, 13):
        length = 2**n
        tables = ["0" * length, "1" * length] + [
            "".join(rng.choice("01") for _ in range(length)) for _ in range(8)
        ]
        for table in tables:
            code = walked_program(table)
            assert len(code) == 4 * length + table.count("1") + 53 * n + 48
            assert len(code) <= 5 * length + 53 * n + 48


def test_packed_character_bound() -> None:
    rng = random.Random(924)
    for n in range(1, 13):
        length = 2**n
        tables = ["0" * length, "1" * length] + [
            "".join(rng.choice("01") for _ in range(length)) for _ in range(8)
        ]
        for table in tables:
            total = sum(int(table[i : i + 2], 2) for i in range(0, length, 2))
            reflected = 2 * total > 3 * (length // 2)
            fill = min(total, 3 * (length // 2) - total)
            constant = 210 if reflected else 164
            code = packed_program(table)
            assert len(code) == 2 * length + fill + 53 * n + constant
            assert len(code) <= 11 * length / 4 + 53 * n + 210
