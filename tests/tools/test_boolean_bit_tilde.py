"""bit_tilde generator tests."""

import pytest

from esolangs import tools as boolean
from tests.generator_support import assert_parity_at_most_doubles


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
    from esolangs.tools.bit_tilde import _program
    from tests.generator_support import assert_shared_program

    language = "bit~"
    table = bit * 256
    plain = _program(table, keep_constant_input=True)
    commands = 7 * 256 + 17 * 8 + 92

    def workspace(_p):
        return 2 * 256 + 49 + (553).bit_length() + (1498).bit_length() + 4

    assert_shared_program(language, table, plain, commands, workspace)


@pytest.mark.parametrize("n", [1, 2, 3, 5, 8, 11])
@pytest.mark.parametrize("bit", "01")
def test_balancing_retains_legacy_constant_shape(n: int, bit: str) -> None:
    from esolangs.tools.bit_tilde import _program
    from tests.generator_support import assert_constant_balanced_shape

    table = bit * (1 << n)
    assert_constant_balanced_shape(
        "bit~", "bit_tilde", table, _program(table, keep_constant_input=True)
    )
