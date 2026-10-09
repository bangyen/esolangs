"""Subleq generator tests."""

import pytest

from tests.generator_support import assert_an_ignored_input_costs


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """One read into ``TMP``."""
    assert_an_ignored_input_costs("Subleq", 6, 11)
