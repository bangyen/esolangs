"""Packlang folds lexical tokens and shortens its unreferenced package name."""

import random

import pytest

import esolangs
from esolangs.interpreters.other._packlang_lex import _tokenize
from esolangs.tools.packlang import packlang
from esolangs.tools.wrap import wrap_program
from tests.generator_support import evaluate_generated


@pytest.mark.parametrize("inputs", [1, 2, 3])
@pytest.mark.medium
def test_every_small_packlang_table_executes_at_the_new_floor(inputs: int) -> None:
    for value in range(1 << (1 << inputs)):
        table = format(value, f"0{1 << inputs}b")
        source = esolangs.generate("Packlang", table, width=1)
        assert max(map(len, source.splitlines())) == 7
        assert evaluate_generated("Packlang", table, width=1) == table


@pytest.mark.parametrize("inputs", [4, 5, 8, 10])
@pytest.mark.parametrize("width", [1, 7, 11, 40, 80])
def test_packlang_lexical_folds_execute_sampled_rows(inputs: int, width: int) -> None:
    table = format(random.Random(inputs).getrandbits(1 << inputs), f"0{1 << inputs}b")
    source = esolangs.generate("Packlang", table, width=width)
    assert max(map(len, source.splitlines())) <= max(width, 7)
    reflowed = wrap_program(source, "packlang", 1)
    assert _tokenize(reflowed) == _tokenize(source)
    for row in [0, 1, len(table) // 2, len(table) - 2, len(table) - 1]:
        bits = [int(bit) for bit in format(row, f"0{inputs}b")]
        stdin = esolangs.encode_inputs("Packlang", bits)
        assert esolangs.run("Packlang", source, stdin=stdin) == table[row]
        assert esolangs.run("Packlang", reflowed, stdin=stdin) == table[row]


def test_packlang_default_and_fitting_source_stay_unchanged() -> None:
    table = "0110"
    assert packlang(table, 80) == packlang(table)
    assert "truthTable" in packlang(table)
    assert "truthTable" not in packlang(table, 1)
