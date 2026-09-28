"""Executed tests for the thisthat boolean generator."""

from itertools import pairwise

import pytest

from esolangs.interpreters.grid_based.thisthat import run
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.thisthat import _Builder, _tree, thisthat


def _run(table: str, row: int) -> tuple[str, int]:
    n = len(table).bit_length() - 1
    bits = f"{row:0{n}b}"
    io = ScriptedIO("".join(f"{bit}\n" for bit in bits))
    run(thisthat(table).splitlines(), io)
    return io.getvalue(), io.reads


@pytest.mark.parametrize("n", [1, 2, pytest.param(3, marks=pytest.mark.medium)])
def test_every_table_through_three_inputs(n: int) -> None:
    width = 1 << n
    for value in range(1 << width):
        table = f"{value:0{width}b}"
        for row, expected in enumerate(table):
            output, reads = _run(table, row)
            assert output == expected, (table, row)
            assert reads == n, (table, row)


def _parity(n: int) -> str:
    return "".join(str(row.bit_count() & 1) for row in range(1 << n))


@pytest.mark.medium
def test_source_growth_is_linear_in_the_table() -> None:
    """Parity keeps every node, so it is the full tree's growth.

    From four inputs, where the tree outgrows the loader row above it.
    """
    sizes = [len(thisthat(_parity(n))) for n in range(1, 14)]
    assert all(right <= 3 * left for left, right in pairwise(sizes[3:]))
    assert max(size / (1 << n) for n, size in enumerate(sizes, 1)) < 300


def _pops(program: str) -> int:
    return program.count("◧")


def test_constants_test_nothing() -> None:
    """The positive control: a constant reads its inputs and prints."""
    for table in ("0" * 8, "1" * 8, "0" * 64):
        program = thisthat(table)
        assert _pops(program) == 0
        n = len(table).bit_length() - 1
        for row in range(0, 1 << n, 1 if n <= 3 else 9):
            bits = f"{row:0{n}b}"
            io = ScriptedIO("".join(f"{bit}\n" for bit in bits))
            run(program.splitlines(), io)
            assert (io.getvalue(), io.reads) == (table[0], n)
    assert len(thisthat("0" * 8)) == 79  # 1,169 before


def test_only_dependent_levels_are_tested() -> None:
    """A level whose halves agree is popped onto the column stack, not tested."""

    def tests(table: str) -> int:
        program = thisthat(table)
        return program.count("◑") + program.count("◒")

    assert tests("00001111") == 1  # the first input alone
    assert tests("01010101") == 1  # the last input alone
    assert tests("00010011") == 4  # the full tree has 7
    # The second input is tested under x0 = 0 and popped under x0 = 1.
    assert tests("00010101") == 4  # 7 unpruned
    assert "⬒" in thisthat("00010101").split("\n", 1)[1]
    for table in ("00110011", "00010101", "01011010"):
        for row, expected in enumerate(table):
            assert _run(table, row) == (expected, 3)


def test_pruning_never_grows_a_table() -> None:
    """No table through three inputs is larger than its unpruned tree.

    ``prune=False`` is the previous tree under the tighter loader: the 256
    three-input tables were 299,264 characters, are 199,936 unpruned, and
    159,628 with ignored inputs projected and agreeing levels skipped.
    """
    for n in (1, 2, 3):
        for value in range(1 << (1 << n)):
            table = f"{value:0{1 << n}b}"
            assert len(thisthat(table)) <= len(_tree(table, prune=False))
    tables = [f"{value:08b}" for value in range(256)]
    assert sum(len(thisthat(table)) for table in tables) == 159_628
    assert sum(len(_tree(table, prune=False)) for table in tables) == 199_936


def test_layout_collisions_abort() -> None:
    builder = _Builder()
    builder.node((0, 0), "▣")
    with pytest.raises(ValueError, match="layout collision"):
        builder.node((0, 0), "◇")
    builder.connect([(1, 0), (2, 0)], "single")
    with pytest.raises(ValueError, match="wire collision"):
        builder.connect([(1, 0), (2, 0)], "double")
