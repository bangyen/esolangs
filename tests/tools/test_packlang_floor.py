"""Packlang folds lexical tokens and shortens its unreferenced package name."""

import random

import pytest

import esolangs
from esolangs.interpreters.other.packlang import _tokenize
from esolangs.tools.packlang import packlang
from esolangs.tools.wrap import wrap_program
from tests.interpreters.packlang_observer import check


@pytest.mark.parametrize(
    "inputs", [4, 5, 8, pytest.param(10, marks=pytest.mark.medium)]
)
@pytest.mark.parametrize("width", [1, 7, 11, 40, 80])
def test_packlang_lexical_folds_execute_sampled_rows(inputs: int, width: int) -> None:
    table = format(random.Random(inputs).getrandbits(1 << inputs), f"0{1 << inputs}b")
    source = esolangs.generate("Packlang", table, width)
    assert max(map(len, source.splitlines())) <= max(width, 7)
    reflowed = wrap_program(source, "packlang", 1)
    assert _tokenize(reflowed) == _tokenize(source)
    for row in [0, 1, len(table) // 2, len(table) - 2, len(table) - 1]:
        bits = [int(bit) for bit in format(row, f"0{inputs}b")]
        stdin = esolangs.encode_inputs("Packlang", bits)
        assert check(source, stdin)["output"] == table[row]
        assert check(reflowed, stdin)["output"] == table[row]


def test_packlang_default_and_fitting_source_stay_unchanged() -> None:
    table = "0110"
    assert packlang(table, 80) == packlang(table)
    assert "truthTable" in packlang(table)
    assert "truthTable" not in packlang(table, 1)
