"""Shared execution and construction checks for reader generators."""

import pytest

from tests.generators.reader_support import _READERS, _TABLES, _read_answer


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
            table = f"{value:0{2**n}b}"
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
