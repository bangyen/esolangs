"""unsquare generator tests."""

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_unsquare,
)
from tests.witness_tables import witnesses


class TestUnsquare:
    """The table lives on the stack; the reads pop down to the answer."""

    @staticmethod
    def _rows(table: str) -> list[str]:
        """Every row of ``table`` as the generated program answers it."""
        n = (len(table) - 1).bit_length()
        program = boolean.unsquare(table)
        return [
            run_unsquare(program, list(format(row, f"0{n}b"))) for row in range(2**n)
        ]

    def test_program_shape(self) -> None:
        """The table is pushed first, then one read an input, then the print."""
        program = boolean.unsquare("0110")
        assert program.startswith("OIIO")  # the table, reversed, one cell a row
        assert program.count("i") == 2  # one read an input
        assert program.endswith("o")

        for value in range(256):
            assert boolean.unsquare(format(value, "08b")).count("i") == 3

    def test_two_bytes_a_row(self) -> None:
        """Size is the table plus its addressing, not a tree over it."""
        for n in range(2, 11):
            table = "".join("01"[(row * row) % 3 % 2] for row in range(2**n))
            size = len(boolean.unsquare(table))
            assert size - 2 * 2**n == 10 * n + 26, n

    @pytest.mark.medium
    def test_every_row_of_every_small_table(self) -> None:
        """The witness tables at n <= 3, every row executed."""
        for n in (1, 2, 3):
            for table in witnesses(n):
                assert "".join(self._rows(table)) == table, table

    def test_inessential_inputs_cost_a_read_not_a_table(self) -> None:
        """An ignored input is consumed by ``iA`` and never widens the table."""
        program = boolean.unsquare("01010101")  # depends on the last input alone
        assert program.count("i") == 3
        assert program.startswith("IOiA")  # two cells, then the first skip
        assert "".join(self._rows("01010101")) == "01010101"

    def test_the_program_is_only_unsquare_commands(self) -> None:
        """Only the characters Unsquare reads are emitted."""
        for table in ("10", "0110", "0001", "11111110"):
            assert set(boolean.unsquare(table)) <= set("+-<>AIOPiox"), table

    @pytest.mark.parametrize("tail", ["0" * 32, "1" * 31 + "0", "0" * 31 + "1"])
    def test_a_long_run_of_cells_is_a_loop_and_runs(self, tail: str) -> None:
        """Even and odd runs, both entries, in front of and behind other cells."""
        table = "01101001100101101001011001101001" + tail
        assert "OA+" in boolean.unsquare(table)
        assert self._rows(table) == list(table)


@pytest.mark.medium
def test_shared_push_body_executes_within_ledger() -> None:
    from esolangs.tools.helpers import essential_inputs, read_at
    from esolangs.tools.unsquare import _runs, _shared_pushes, unsquare
    from tests.generator_support import assert_shared_program

    first = "0001011101101001" * 4
    second = "0110100100010111" * 4
    third = "0011010101010011" * 4
    table = first + first + second + third
    used = essential_inputs(table, 8) or [0]
    bits = read_at(table, used, 8)[::-1]
    shared = _shared_pushes(bits, 8, len(used))
    assert shared is not None
    program = unsquare(table)
    assert program.startswith(shared)
    plain = _runs(bits)[0] + program[len(shared) :]
    assert_shared_program(
        "Unsquare",
        table,
        plain,
        4 * 256 + 79 * 8 + 22,
        lambda p: 256 + 12 + len(p).bit_length() + (len(p) - 33).bit_length() + 8,
    )


@pytest.mark.medium
def test_balance_retains_the_square_unshared_initializer() -> None:
    from esolangs import generate
    from esolangs.tools.unsquare import _program
    from esolangs.tools.wrap import balance_program, balance_score

    first = "0001011101101001" * 4
    table = first * 2 + "0110100100010111" * 4 + "0011010101010011" * 4
    old = balance_program(_program(table, share=False), "unsquare")
    program = generate("Unsquare", table, balance=True)
    assert balance_score(program) == balance_score(old) == (0, 232, 15)
    for row in (0, 1, 127, 128, 255):
        assert run_unsquare(program, list(format(row, "08b"))) == table[row]


@pytest.mark.medium
@pytest.mark.parametrize("bit", "01")
def test_every_constant_row_within_written_state_bound(bit: str) -> None:
    from esolangs.tools.unsquare import _program
    from tests.generator_support import assert_shared_program

    language = "Unsquare"
    table = bit * 256
    plain = _program(table, share=True, keep_constant_input=True)
    commands = 4 * 256 + 79 * 8 + 22

    def workspace(p):
        return 256 + 12 + len(p).bit_length() + max(0, len(p) - 33).bit_length() + 8

    assert_shared_program(language, table, plain, commands, workspace)


@pytest.mark.parametrize("n", [1, 2, 3, 5, 8, 11])
@pytest.mark.parametrize("bit", "01")
def test_balancing_retains_legacy_constant_shape(n: int, bit: str) -> None:
    from esolangs.tools.unsquare import _program
    from tests.generator_support import assert_constant_balanced_shape

    table = bit * (1 << n)
    assert_constant_balanced_shape(
        "Unsquare",
        "unsquare",
        table,
        _program(table, share=True, keep_constant_input=True),
    )
