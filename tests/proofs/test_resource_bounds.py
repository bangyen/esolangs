"""Executed controls for forward dispatch and bounded byte-index cascades."""

import pytest

from scripts.screens.resources import audit, corpus


@pytest.mark.medium
@pytest.mark.parametrize(
    ("language", "n", "family"), [("Sophie", 3, "parity"), ("BFStack", 8, "dense")]
)
def test_resource_bounds(language: str, n: int, family: str) -> None:
    result = audit(language, n, corpus(n)[family])
    assert result["source_utf8_bits"] == 8 * result["source_units"]


@pytest.mark.medium
@pytest.mark.parametrize("n", [3])
def test_subleq_packed_store_and_integer_bounds(n: int) -> None:
    for table in corpus(n).values():
        result = audit("Subleq", n, table)
        assert result["peak_data_bits"] >= result["peak_memory_cells"]
