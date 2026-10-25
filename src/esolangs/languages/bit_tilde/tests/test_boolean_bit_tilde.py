"""bit_tilde generator tests."""

import pytest

from esolangs.languages import generators as boolean
from tests.support.generator_support import assert_parity_at_most_doubles


class TestBitTilde:
    def test_single_read_and_output(self) -> None:
        """One read per input and a single final output."""
        program = boolean.bit_tilde("0110")
        # The prologue paints the table and walks to the top of it, so the
        # opening is moves and flips -- no loop, read or print among them.
        assert set(program[: program.index(")")]) <= {">", "~"}
        assert program.count(")") == 2
        assert program.count("(") == 1
        assert program.endswith("(")


@pytest.mark.medium
def test_parity_source_at_most_doubles_per_input() -> None:
    assert_parity_at_most_doubles(boolean.bit_tilde, (7, 8), 255)


@pytest.mark.medium
@pytest.mark.parametrize("bit", "01")
def test_every_constant_row_within_written_state_bound(bit: str) -> None:
    from tests.support.generator_support import assert_shared_program

    language = "bit~"
    table = bit * 256
    commands = 7 * 256 + 17 * 8 + 92

    def workspace(_p):
        return 2 * 256 + 49 + (553).bit_length() + (1498).bit_length() + 4

    assert_shared_program(language, table, None, commands, workspace)


def test_xor_window_scratch_read_comes_back_eight() -> None:
    """An ignored input is read into a scratch window eight cells over.

    The excursion goes out eight and must come back eight:
    coming back nine leaves the pointer a cell left of the
    window, the fix-up plants land a cell off, and the program
    walks off the tape.  Each table below is affine with an
    ignored input, so the xor-window form is the shipped one.
    """
    from tests.generators.boolean_runners import _runner

    run = _runner("bit_tilde")
    for table in ("0011", "1100", "10100101"):
        n = len(table).bit_length() - 1
        program = boolean.bit_tilde(table)
        for row in range(1 << n):
            bits = list(f"{row:0{n}b}")
            assert run(program, bits) == table[row]
