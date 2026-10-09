"""Painfuck through the shared API, CLI and machinery."""

from tests.test_vm import assert_random_steps_reproduce


def test_stepping_through_the_random_instruction_is_reproducible() -> None:
    """Its random instruction steps the same way twice under one seed."""
    assert_random_steps_reproduce("Painfuck", "y")
