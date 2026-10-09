"""Tests for the Subleq interpreter."""

import pytest

from tests.raises import assert_halts_with_hint, assert_rejected_with_hint


@pytest.mark.medium
def test_bad_programs_carry_a_repair_hint() -> None:
    assert_rejected_with_hint("Subleq", "x", "decimal integers")
    assert_halts_with_hint("Subleq", "0 0", "incomplete Subleq", "three addresses")
