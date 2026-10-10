"""Subleq generator tests."""

from typing import Any

import pytest

from tests.generator_support import assert_an_ignored_input_costs


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """One read into ``TMP``."""
    assert_an_ignored_input_costs("Subleq", 6, 11)


def _bounds(profile: dict[str, Any]) -> None:
    """The construction bounds the resource audit holds this generator to."""
    n = profile["inputs"]
    rows = 1 << n
    commands = profile["worst_row_commands"]
    memory = profile["peak_memory_cells"]
    stack = profile["peak_stack_items"]
    # Eight instructions per input, fewer than 60 fixed instructions and
    # 18 registers, then ceil(T/n) chunks. Selection costs <16T commands;
    # repeated unary division costs <32T, with <64n+512 setup commands.
    cell_bound = 24 * n + 200 + (rows + n - 1) // n
    assert commands <= 64 * rows + 64 * n + 512
    assert memory <= cell_bound
    assert stack == profile["peak_control_stack_items"] == 0
    assert profile["peak_integer_bits"] <= max(n + 1, cell_bound.bit_length() + 1, 7)
    assert profile["peak_machine_bits"] <= (
        cell_bound * max(n + 1, cell_bound.bit_length() + 1, 7)
        + cell_bound.bit_length()
    )


@pytest.mark.medium
def test_packed_store_and_integer_bounds() -> None:
    """The resource audit's data bits cover every memory cell it peaks at."""
    from scripts.screens.resources import audit, corpus

    for table in corpus(3).values():
        result = audit("Subleq", 3, table, _bounds)
        assert result["peak_data_bits"] >= result["peak_memory_cells"]
