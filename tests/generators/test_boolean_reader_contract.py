"""Shared execution and construction checks for reader generators."""

import pytest

from tests.generators.reader_support import _READERS, _TABLES, _read_answers


@pytest.mark.parametrize("name", sorted(_READERS))
@pytest.mark.parametrize("table", _TABLES)
def test_a_reader_answers_every_row(name: str, table: str) -> None:
    n = len(table).bit_length() - 1
    for row, (expected, (printed, reads)) in enumerate(
        zip(table, _read_answers(name, table), strict=True)
    ):
        assert printed == expected, (name, table, row)
        assert reads == n, (name, table, row)


@pytest.mark.parametrize("name", sorted(_READERS))
@pytest.mark.slow
def test_a_reader_answers_every_table_to_three_inputs(name: str) -> None:
    """Together with the fast corpus, exhaust every table and row through n=3."""
    for n in (1, 2, 3):
        for value in range(2 ** (2**n)):
            table = f"{value:0{2**n}b}"
            if table in _TABLES:
                continue
            for row, (expected, (printed, reads)) in enumerate(
                zip(table, _read_answers(name, table), strict=True)
            ):
                assert printed == expected, (name, table, row)
                assert reads == n


def test_reader_sweep_rejects_missing_extra_or_incorrect_answers(monkeypatch):
    name = next(iter(_READERS))
    for answers in (
        [],
        [("0", 1)],
        [("0", 1), ("1", 1), ("0", 1)],
        [("1", 1), ("0", 1)],
        [("0", 0), ("1", 0)],
    ):
        monkeypatch.setattr(
            __name__ + "._read_answers", lambda *_args, batch=answers: iter(batch)
        )
        with pytest.raises((AssertionError, ValueError)):
            test_a_reader_answers_every_row(name, "01")
