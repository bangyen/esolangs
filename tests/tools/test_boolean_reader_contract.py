"""Shared execution and construction checks for reader generators."""

import pytest

from esolangs import tools as boolean
from tests.tools.reader_support import _READERS, _TABLES, _read_answer


@pytest.mark.parametrize("name", sorted(_READERS))
@pytest.mark.parametrize("table", _TABLES)
def test_a_reader_answers_every_row(name: str, table: str) -> None:
    n = len(table).bit_length() - 1
    for row in range(2**n):
        printed, reads = _read_answer(name, table, row)
        assert printed == table[row], (name, table, row)
        assert reads == n, (name, table, row)


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


def test_the_emissions_grow_by_a_line() -> None:
    """Successive differences at a fixed parity quadruple, exactly."""
    from tests.tools.plain_oracles import false_plain as _plain
    from tests.tools.plain_oracles import unlambda_plain as _plain_unlambda

    # FALSE's and Unlambda's shipped builds fold and share this table's
    # subtrees, so their plain trees are the ones measured.
    trees = (lambda table: _plain(table, len(table).bit_length() - 1),)
    for generate in (*trees, boolean.thue, _plain_unlambda):
        sizes = [len(generate("01" * (2 ** (n - 1)))) for n in (4, 6, 8)]
        assert (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) == 4.0
