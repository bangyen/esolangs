"""Dig through the shared API, CLI and machinery."""

from tests.vm.test_vm_protocol import assert_starts_downward


def test_the_first_move_is_down_the_rows() -> None:
    """It begins vertically, so ``VM.ip``'s first component moves first."""
    assert_starts_downward("Dig")
