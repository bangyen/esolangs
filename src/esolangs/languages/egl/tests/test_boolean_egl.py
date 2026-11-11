"""Execution tests for the EGL boolean generator."""

import itertools
import random

import pytest

from esolangs.languages.egl import generator as tools
from esolangs.languages.egl.generator import _balance, _wrap
from esolangs.languages.egl.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import (
    assert_an_ignored_input_costs,
    assert_constant_output,
    constant_programs,
)


def execute(program: str, bits: tuple[int, ...]) -> tuple[str, int]:
    io = ScriptedIO("".join(f"{bit}" for bit in bits))
    run(program, io)
    return io.getvalue(), io.position()


def test_the_walk_is_branch_free() -> None:
    """One guard and one counter loop an input, no other: the table is not a tree."""
    _check_folded()
    assert_analysis_complement("EGL", "input_weights")
    assert_analysis_complement("EGL", "symmetric_weights", "0110")
    program = tools.egl("01101001")
    assert program.count("(") == 6
    assert program.count("(->") == 3


@pytest.mark.parametrize("n", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_reads_into_scratch_and_prints_a_literal(n: int, bit: str) -> None:
    if n == 1 and bit == "0":
        _check_constants()
    table = bit * (1 << n)
    default = tools.egl(table)
    programs = [tools.egl(table, width) for width in (None, 1, 20)]
    for program in programs:
        assert program.startswith("2,1:")
        assert program.count("x") == n
        assert "(" not in program
    for program in [*programs, _balance(table, default)]:
        for bits in itertools.product((0, 1), repeat=n):
            assert execute(program, bits) == (bit, n)


def test_size_is_table_content_only() -> None:
    """Two asymmetric tables of one arity and one popcount render alike in length.

    Both read every input: an ignored one is a bare ``x`` and drops the table
    to the rest's.  A symmetric table (parity) takes the count route instead.
    """
    assert len(tools.egl("01011001")) == len(tools.egl("01110001"))


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


def _check_constants() -> None:
    for n, bit, _options, program in constant_programs("EGL", range(1, 13)):
        for row in ("0" * n, "1" * n):
            io = ReadFirstIO(row + "7", expected=n)
            assert_constant_output(run, program, io, bit, n)
            assert io.input_char() == ord("7")


def _check_folded() -> None:
    from esolangs.languages.egl.tests.ablations import ablate
    from scripts.docs.resource_evidence import resource_bounds

    bounds = resource_bounds("EGL")
    execution = bounds["execution"].formula
    workspace = bounds["workspace"].formula

    for n in (4, 7):
        rng = random.Random(n)
        table = "".join(rng.choice("01") for _ in range(1 << n))
        program = tools.egl(table)
        assert program == ablate(table, "default")
        assert len(program) < len(ablate(table, "folded_rows"))
        for text in (program, _wrap(program, 1)):
            for row in (0, (1 << n) - 1):
                io = ScriptedIO(f"{row:0{n}b}7")
                machine = _Machine(text, io)
                written = WrittenState(machine.workspace_snapshot())
                steps = 0
                while not machine.halted:
                    assert not io.getvalue()
                    machine.step()
                    written.sample(machine.workspace_snapshot())
                    steps += 1
                assert io.getvalue() == table[row]
                assert io.reads == n
                assert not io.past_end
                assert steps <= execution(n, text)
                assert written.bits <= workspace(n, text)
                assert io.input_char() == ord("7")
