"""Execution tests for the EGL boolean generator."""

import itertools

from esolangs import tools
from esolangs.interpreters.grid_based.egl import run
from esolangs.interpreters.io import ScriptedIO


def execute(program: str, bits: tuple[int, ...]) -> tuple[str, int]:
    io = ScriptedIO("".join(f"{bit}" for bit in bits))
    run(program, io)
    return io.getvalue(), io.position()


def test_the_walk_is_branch_free() -> None:
    """One guard an input, and no other loop: the table is not a tree."""
    program = tools.egl("01101001")
    assert program.count("(") == 3


def test_size_is_table_content_only() -> None:
    """Two tables of one arity and one popcount render to the same length.

    Both read every input: an ignored one is a bare ``x`` and drops the table
    to the rest's.
    """
    assert len(tools.egl("01101001")) == len(tools.egl("01110001"))


def test_wrapped_programs_still_compute_the_table() -> None:
    table = "10010110"
    for width in (5, 20, 80):
        program = tools.egl(table, width)
        assert max(map(len, program.split("\n"))) <= max(width, len("8,2:"))
        for bits in itertools.product((0, 1), repeat=3):
            index = int("".join(map(str, bits)), 2)
            assert execute(program, bits) == (table[index], 3)
