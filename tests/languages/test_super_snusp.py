"""Super SNUSP through the shared API, CLI and machinery."""

from tests.test_vm_protocol import assert_one_row_moves_along_it


def test_its_one_row_program_moves_along_the_columns() -> None:
    """The row component of ``VM.ip`` stays put on a one-row program."""
    assert_one_row_moves_along_it("Super SNUSP")
