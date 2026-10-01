"""Executed controls for forward dispatch and bounded byte-index cascades."""

import pytest

from scripts.screens.resources import audit, corpus


@pytest.mark.medium
@pytest.mark.parametrize("language", ["Sophie", "BFStack"])
@pytest.mark.parametrize("n", [1, 3, 7, 8])
def test_resource_bounds(language: str, n: int) -> None:
    for table in corpus(n).values():
        audit(language, n, table)
