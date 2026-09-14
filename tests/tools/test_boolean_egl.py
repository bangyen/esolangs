"""Execution tests for the EGL boolean generator."""

import itertools

import pytest

from esolangs import tools
from esolangs.interpreters.grid_based.egl import run
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.egl import _egl_ordered


def execute(program: str, bits: tuple[int, ...]) -> tuple[str, int]:
    io = ScriptedIO("".join(f"{bit}\n" for bit in bits))
    run(program, io)
    return io.getvalue(), io.position()


@pytest.mark.parametrize(
    "table", ["00", "01", "10", "11", "0001", "0110", "1110", "01101001"]
)
def test_truth_tables(table: str) -> None:
    n = len(table).bit_length() - 1
    program = tools.egl(table)
    for bits in itertools.product((0, 1), repeat=n):
        index = int("".join(map(str, bits)), 2)
        output, reads = execute(program, bits)
        assert output == table[index]
        assert reads == n


def test_constant_subtrees_fold() -> None:
    assert len(tools.egl("00001111")) < len(tools.egl("01101001"))


def test_input_reordering_folds_a_scattered_table() -> None:
    table = "10101010"
    assert len(tools.egl(table)) < len(_egl_ordered(table, (0, 1, 2)))


def test_input_reordering_never_grows_a_program() -> None:
    for value in range(256):
        table = f"{value:08b}"
        assert len(tools.egl(table)) <= len(_egl_ordered(table, (0, 1, 2)))


def test_reordered_programs_compute_the_table() -> None:
    for value in range(256):
        table = f"{value:08b}"
        test_truth_tables(table)
