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
        x * (x - 1) ** 2 * (x + 1) ** 2 * (x**3 - 7 * x**2 + 1)
    )
    assert 6.97 < growth() < 6.98
    assert abs(growth() ** 3 - 7 * growth() ** 2 + 1) < 1e-12
    lower = math.log(2) ** 2 / (math.log(growth()) * math.log(10))
    upper = (435 / 448) * math.log10(2)
    assert lower == pytest.approx(0.1073911319728899)
    assert upper / lower == pytest.approx(2.7217773468285684)


def test_pointer_pair_and_totality_controls() -> None:
    # The tape grows left, so `<>` at cell zero returns to its cell.
    code = "+<>."
    assert normalize(code) == "+."
    for program in (code, "+."):
        io = ScriptedIO("")
        run_bf(program, io)
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
def test_normalized_truth_witnesses(n: int) -> None:
    for value in range(0, 2 ** (2**n), 7):
        table = format(value, f"0{2**n}b")
        code = "+- -+ >< [][..]".replace(" ", "") + counter_program(table).replace(
            ",", "+--++,"
        )
        normal = normalize(code)
        assert not any(a + b in FORBIDDEN for a, b in pairwise(normal))
        assert len(normal) < len(code)
        assert normalize(normal) == normal
        for row in range(2**n):
            bits = "".join(format(row, f"0{n}b"))
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


class _PrintedError(Exception):
    pass


class _FirstOutputIO(ScriptedIO):
    def print_char(self, value: str) -> None:
        super().print_char(value)
        raise _PrintedError


@pytest.mark.medium
@pytest.mark.parametrize("n", range(1, 4))
def test_prefix_normalized_witnesses(n: int) -> None:
    from tests.proofs._factor_normal import prefix_normalize

    for value in range(0, 2 ** (2**n), 7):
        table = format(value, f"0{2**n}b")
        source = counter_program(table)
        normal = prefix_normalize(source)
        assert prefix_normalize(normal) == normal
        assert "][" not in normal
        assert "]." not in normal
        assert all(first != "." or second == "]" for first, second in pairwise(normal))
        for row in range(2**n):
            bits = "".join(format(row, f"0{n}b"))
            io = _FirstOutputIO(bits)
            with pytest.raises(_PrintedError):
                run_bf(normal, io)
            assert io.getvalue() == table[row]


@pytest.mark.medium
def test_prefix_semantics_is_not_ordinary_halting() -> None:
    from tests.proofs._factor_normal import prefix_normalize

    source = ",[[-]" + "+" * 48 + ".[-]][+.]"
    normal = prefix_normalize(source)
    for bit in "01":
        original = ScriptedIO(bit)
        run_bf(source, original)
        assert original.getvalue() == "0"
        io = _FirstOutputIO(bit)
        with pytest.raises(_PrintedError):
            run(_render(normal), io)
        assert io.getvalue() == "0"
    io = ScriptedIO("0")
    machine = _Machine(normal, io)
    for _ in range(2000):
        machine.step()
    assert not machine.halted
    assert len(io.getvalue()) > 1


def test_prefix_word_matrix() -> None:
    from tests.proofs._factor_normal import prefix_growth

    forbidden = FORBIDDEN | {"][", "]."}
    matrix = sympy.Matrix(
        [
            [int(a + b not in forbidden and (a != "." or b == "]")) for b in ALPHABET]
            for a in ALPHABET
        ]
    )
    x = sympy.Symbol("x")
    assert matrix.charpoly(x).as_expr() == sympy.expand(
        x**2 * (x - 1) ** 2 * (x + 1) * (x**3 - 6 * x**2 + 1)
    )
    assert 5.97 < prefix_growth() < 5.98
