"""Execute the single-output normal form and check its exact word count."""

import math
from itertools import pairwise

import pytest
import sympy

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.brainfuck import _Machine
from esolangs.interpreters.tape_based.brainfuck import run as run_bf
from esolangs.interpreters.tape_based.factor import run
from tests.proofs._factor_counter import counter_program
from tests.proofs._factor_normal import ALPHABET, FORBIDDEN, growth, normalize
from tests.proofs.test_factor_print import _render


def test_normal_word_matrix() -> None:
    matrix = sympy.Matrix(
        [
            [int(first + second not in FORBIDDEN) for second in ALPHABET]
            for first in ALPHABET
        ]
    )
    x = sympy.Symbol("x")
    assert matrix.charpoly(x).as_expr() == sympy.expand(
        x**3 * (x - 1) * (x + 1) * (x**3 - 7 * x**2 - x + 2)
    )
    assert 7.10 < growth() < 7.11
    assert abs(growth() ** 3 - 7 * growth() ** 2 - growth() + 2) < 1e-12
    lower = math.log(2) ** 2 / (math.log(growth()) * math.log(10))
    upper = (435 / 448) * math.log10(2)
    assert lower == pytest.approx(0.10644418816056818)
    assert upper / lower == pytest.approx(2.7459906952662383)


def test_pointer_clamp_and_totality_controls() -> None:
    code = "+<>."
    assert normalize(code) == code
    io = ScriptedIO("")
    run_bf(code, io)
    assert io.getvalue() == "\x00"
    io = ScriptedIO("")
    run_bf(code.replace("<>", ""), io)
    assert io.getvalue() == "\x01"
    # An empty loop may only be deleted on halting inputs.
    machine = _Machine("+[]", ScriptedIO(""))
    for _ in range(30):
        machine.step()
    assert not machine.halted
    assert normalize("+[]") == "+"
    assert normalize("..") == ""  # two outputs lies outside the contract


@pytest.mark.medium
@pytest.mark.parametrize("n", range(1, 4))
@pytest.mark.parametrize("partition", range(4))
def test_normalized_truth_witnesses(n: int, partition: int) -> None:
    for value in range(partition, 2 ** (2**n), 4):
        table = format(value, f"0{2**n}b")
        code = "+- -+ >< [][..]".replace(" ", "") + counter_program(table).replace(
            ",", "+--++,"
        )
        normal = normalize(code)
        assert not any(a + b in FORBIDDEN for a, b in pairwise(normal))
        assert len(normal) < len(code)
        assert normalize(normal) == normal
        for row in range(2**n):
            bits = "\n".join(format(row, f"0{n}b"))
            original, reduced = ScriptedIO(bits), ScriptedIO(bits)
            run_bf(code, original)
            run_bf(normal, reduced)
            assert original.getvalue() == reduced.getvalue() == table[row]


@pytest.mark.medium
@pytest.mark.parametrize("table", ["00", "01", "10", "11"])
def test_normalized_factor_executes(table: str) -> None:
    code = "+- -+ >< [][..]".replace(" ", "") + counter_program(table).replace(
        ",", "+--++,"
    )
    for source in (code, normalize(code)):
        program = _render(source)
        for row in range(2):
            io = ScriptedIO(str(row))
            run(program, io)
            assert io.getvalue() == table[row]
