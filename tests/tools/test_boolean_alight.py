"""Alight generator tests."""

import pytest

from tests.generator_support import assert_an_ignored_input_costs


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """``inp r;``, overwritten by the lookup."""
    assert_an_ignored_input_costs("Alight", 6, 6)
