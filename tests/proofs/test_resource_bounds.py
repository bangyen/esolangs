"""Executed controls for forward dispatch and bounded byte-index cascades."""

import pytest

from esolangs.registry import LANGUAGES
from scripts.screens.resources import audit, corpus

_SUBLEQ = "Subleq"
#: The audit's languages that are still registered; one removed drops out.
_CASES = [
    case
    for case in [("Sophie", 3, "parity"), ("BFStack", 8, "dense")]
    if case[0] in LANGUAGES
]


@pytest.mark.medium
@pytest.mark.parametrize(("language", "n", "family"), _CASES)
def test_resource_bounds(language: str, n: int, family: str) -> None:
    result = audit(language, n, corpus(n)[family])
    assert result["source_utf8_bits"] == 8 * result["source_units"]


@pytest.mark.medium
@pytest.mark.parametrize("n", [3] if _SUBLEQ in LANGUAGES else [])
def test_subleq_packed_store_and_integer_bounds(n: int) -> None:
    for table in corpus(n).values():
        result = audit(_SUBLEQ, n, table)
        assert result["peak_data_bits"] >= result["peak_memory_cells"]
