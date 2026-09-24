"""Execution tests for the EGL boolean generator."""

import itertools

import pytest

from esolangs import tools
from esolangs.interpreters.grid_based.egl import run
from esolangs.interpreters.io import ScriptedIO


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


def test_every_three_input_table_runs() -> None:
    for value in range(256):
        test_truth_tables(f"{value:08b}")


def test_the_walk_is_branch_free() -> None:
    """One guard an input, and no other loop: the table is not a tree."""
    program = tools.egl("01101001")
    assert program.count("(") == 3


def test_size_is_table_content_only() -> None:
    """Two tables of one arity and one popcount render to the same length."""
    assert len(tools.egl("01101001")) == len(tools.egl("00001111"))


def test_wrapped_programs_still_compute_the_table() -> None:
    table = "10010110"
    for width in (5, 20, 80):
        program = tools.egl(table, width)
        assert max(map(len, program.split("\n"))) <= max(width, len("8,2:"))
        for bits in itertools.product((0, 1), repeat=3):
            index = int("".join(map(str, bits)), 2)
            assert execute(program, bits) == (table[index], 3)
