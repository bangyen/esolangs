"""Execution tests for the EGL boolean generator."""

import itertools

import pytest

from esolangs.languages import generators as tools
from esolangs.languages.egl.interpreter import run
from esolangs.runtime.io import ScriptedIO
from tests.support.generator_support import assert_an_ignored_input_costs


def execute(program: str, bits: tuple[int, ...]) -> tuple[str, int]:
    io = ScriptedIO("".join(f"{bit}" for bit in bits))
    run(program, io)
    return io.getvalue(), io.position()


def test_the_walk_is_branch_free() -> None:
    """One guard an input, and no other loop: the table is not a tree."""
    program = tools.egl("01101001")
    assert program.count("(") == 3


@pytest.mark.parametrize("n", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_reads_into_scratch_and_prints_a_literal(n: int, bit: str) -> None:
    from esolangs.languages.egl.generator import _balance

    table = bit * (1 << n)
    default = tools.egl(table)
    programs = [tools.egl(table, width) for width in (None, 1, 20)]
    for program in programs:
        assert program.startswith("2,1:")
        assert program.count("x") == n
        assert "(" not in program
    # Balance may keep the legacy lookup when it is squarer (n=3: 20x10).
    for program in [*programs, _balance(table, default)]:
        for bits in itertools.product((0, 1), repeat=n):
            assert execute(program, bits) == (bit, n)


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


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """A bare ``x``."""
    assert_an_ignored_input_costs("EGL", 6, 1)
