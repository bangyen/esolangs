"""Tests for the Subleq interpreter."""

import pytest

from tests.raises import assert_rejected_with_hint


@pytest.mark.medium
def test_malformed_source_carries_a_repair_hint() -> None:
    assert_rejected_with_hint("Subleq", "x", "decimal integers")
