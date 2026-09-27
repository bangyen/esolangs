"""Executed tests for the four classic-language boolean generators.

FALSE, Thue and Unlambda read a line per bit and print the answer; FRACTRAN
has no I/O, so its bits are embedded and the answer is the value its run
stops on.  Every assertion here runs the generated program: the exhaustive
sweeps cover ``n <= 3``, which is 256 tables and 2,048 executed rows apiece.
"""

import pytest

from esolangs import tools as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fractran import run as run_fractran
from esolangs.interpreters.other.thue import run as run_thue
from esolangs.interpreters.other.unlambda import run as run_unlambda
from esolangs.interpreters.randomness import Seeded
from esolangs.interpreters.stack_based.false import run as run_false
from esolangs.tools.fractran import PAIR as FRACTRAN_PAIR
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs

#: The line-reading three, each as ``(generator, interpreter run)``.
_READERS = {
    "false": (boolean.false, run_false),
    "thue": (boolean.thue, run_thue),
    "unlambda": (boolean.unlambda, run_unlambda),
}

_TABLES = [
    "01",  # identity
    "10",  # NOT
    "0001",  # AND
    "1110",  # NAND
    "0110",  # XOR
    "00000000",  # constant, which folds all the way down
    "01101001",  # parity, which folds nothing
    "10100101",
    "1000000000000000",  # AND4
]


def _bits(row: int, n: int) -> list[int]:
    return [(row >> (n - 1 - i)) & 1 for i in range(n)]


def _read_answer(name: str, table: str, row: int) -> tuple[str, int]:
    """Return what the generated program printed, and how many lines it read."""
    generate, run = _READERS[name]
    n = len(table).bit_length() - 1
    io = ScriptedIO("".join(f"{bit}\n" for bit in _bits(row, n)))
    run(generate(table), io)
    return io.getvalue(), io.reads


def _fractran_answer(table: str, row: int) -> str:
    """Return what the instantiated FRACTRAN program stopped on."""
    n = len(table).bit_length() - 1
    template = boolean.fractran(table)
    program = fill_runs(template, TEMPLATE_CHAR, [FRACTRAN_PAIR] * n, _bits(row, n))
    io = ScriptedIO("")
    run_fractran(program, io)
    return io.getvalue()


@pytest.mark.parametrize("name", sorted(_READERS))
@pytest.mark.parametrize("table", _TABLES)
def test_a_reader_answers_every_row(name: str, table: str) -> None:
    n = len(table).bit_length() - 1
    for row in range(2**n):
        printed, reads = _read_answer(name, table, row)
        assert printed == table[row], (name, table, row)
        assert reads == n, (name, table, row)


@pytest.mark.parametrize("table", _TABLES)
def test_fractran_answers_every_row(table: str) -> None:
    n = len(table).bit_length() - 1
    for row in range(2**n):
        answer = "2" if table[row] == "1" else "1"
        assert _fractran_answer(table, row) == answer, (table, row)


@pytest.mark.parametrize("name", sorted(_READERS))
@pytest.mark.slow
def test_a_reader_answers_every_table_to_three_inputs(name: str) -> None:
    """Exhaustive: every table at ``n <= 3``, every row of each."""
    for n in (1, 2, 3):
        for value in range(2 ** (2**n)):
            table = bin(value)[2:].zfill(2**n)
            for row in range(2**n):
                printed, reads = _read_answer(name, table, row)
                assert printed == table[row], (name, table, row)
                assert reads == n


@pytest.mark.slow
def test_fractran_answers_every_table_to_three_inputs() -> None:
    for n in (1, 2, 3):
        for value in range(2 ** (2**n)):
            table = bin(value)[2:].zfill(2**n)
            for row in range(2**n):
                answer = "2" if table[row] == "1" else "1"
                assert _fractran_answer(table, row) == answer, (table, row)


@pytest.mark.parametrize("name", sorted(_READERS))
def test_a_constant_table_still_reads_every_input(name: str) -> None:
    """Folding shortens the body; it must not drop the reads."""
    printed, reads = _read_answer(name, "00000000", 5)
    assert printed == "0"
    assert reads == 3


def test_folding_shortens_a_constant_table() -> None:
    """The three tree generators collapse a table whose rows agree."""
    for name in ("false", "unlambda"):
        generate, _run = _READERS[name]
        assert len(generate("00000000")) < len(generate("01101001")), name
    assert len(boolean.fractran("00000000")) < len(boolean.fractran("01101001"))


def test_thue_spells_the_table_once_and_its_rules_are_fixed() -> None:
    """Its emission is the table plus a constant: ``T + 199`` characters."""
    sizes = [len(boolean.thue("01" * (2 ** (n - 1)))) for n in (1, 2, 3, 4)]
    assert sizes == [2**n + 199 for n in (1, 2, 3, 4)]


@pytest.mark.parametrize("table", _TABLES)
def test_thue_never_leaves_the_draw_a_choice(table: str) -> None:
    """Every state a generated program reaches offers exactly one rewrite.

    Thue picks the rewrite at random, by spec, and the interpreter draws.
    What makes these programs reproducible anyway is this invariant, so it is
    asserted by running them rather than argued in a docstring: one applicable
    rule at one position, in every state, on every row.
    """
    from esolangs.interpreters.other.thue import _Machine, _matches

    n = len(table).bit_length() - 1
    program = boolean.thue(table)
    for row in range(2**n):
        stdin = "".join(f"{bit}\n" for bit in _bits(row, n))
        machine = _Machine(program, ScriptedIO(stdin), Seeded(row))
        while not machine.halted:
            found = _matches(machine.state, machine.rules)
            assert len(found) == 1, (table, row, machine.state[:60], found)
            machine.step()


@pytest.mark.parametrize("table", _TABLES)
def test_thue_answers_the_same_under_every_draw(table: str) -> None:
    """Three seeds and the unseeded ``secrets`` draw agree, row by row."""
    n = len(table).bit_length() - 1
    program = boolean.thue(table)
    for row in range(2**n):
        stdin = "".join(f"{bit}\n" for bit in _bits(row, n))
        answers = set()
        for rng in (Seeded(0), Seeded(1), Seeded(9), None):
            io = ScriptedIO(stdin)
            run_thue(program, io, rng)
            answers.add(io.getvalue())
        assert answers == {table[row]}, (table, row, answers)


def test_the_emissions_grow_by_a_line() -> None:
    """Successive differences at a fixed parity quadruple, exactly."""
    for generate in (boolean.false, boolean.thue, boolean.unlambda):
        sizes = [len(generate("01" * (2 ** (n - 1)))) for n in (4, 6, 8)]
        assert (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) == 4.0


def test_fractran_runs_in_a_step_per_level() -> None:
    """At most one step a level, one a cleared prime, and the leaf."""
    from esolangs.interpreters.other.fractran import _Machine

    n = 3
    table = "01101001"
    template = boolean.fractran(table)
    for row in range(2**n):
        program = fill_runs(template, TEMPLATE_CHAR, [FRACTRAN_PAIR] * n, _bits(row, n))
        machine = _Machine(program, ScriptedIO(""))
        steps = 0
        while not machine.halted:
            machine.step()
            steps += 1
        assert steps <= 2 * n + 2, (row, steps)
