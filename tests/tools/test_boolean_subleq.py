"""Subleq generator tests."""

import pytest

from tests.generator_support import assert_an_ignored_input_costs


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """One read into ``TMP``."""
    assert_an_ignored_input_costs("Subleq", 6, 11)


@pytest.mark.medium
def test_packed_store_and_integer_bounds() -> None:
    """The resource audit's data bits cover every memory cell it peaks at."""
    from scripts.screens.resources import audit, corpus

    for table in corpus(3).values():
        result = audit("Subleq", 3, table)
        assert result["peak_data_bits"] >= result["peak_memory_cells"]
