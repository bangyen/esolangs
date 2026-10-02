"""bfstack generator tests."""

import random

import pytest

import esolangs
from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_bfstack,
)


class TestBfstack:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1000000000000000", 4),  # AND4
            ("1111111111111111", 4),  # constant one
        ],
    )
    @pytest.mark.medium
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.bfstack(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bfstack(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.medium
    @pytest.mark.parametrize("n", [7, 8, 9, 12])
    def test_byte_index_boundaries(self, n: int) -> None:
        """Seven-input blocks preserve the sentinel and high input bits."""
        rng = random.Random(n)
        table = "".join(rng.choice("01") for _ in range(1 << n))
        program = boolean.bfstack(table)
        rows = (
            range(1 << n)
            if n <= 9
            else sorted(
                {
                    0,
                    127,
                    128,
                    255,
                    256,
                    2047,
                    2048,
                    4095,
                    *rng.sample(range(1 << n), 32),
                }
            )
        )
        for row in rows:
            bits = [str((row >> i) & 1) for i in range(n - 1, -1, -1)]
            assert run_bfstack(program, bits) == table[row], (n, row)

    @pytest.mark.medium
    @pytest.mark.parametrize("bit", "01")
    def test_wide_constant_blocks_consume_every_input(self, bit: str) -> None:
        """Folded blocks drain their inputs and leave only one answer."""
        table = bit * 256 + ("1" if bit == "0" else "0") * 256
        program = boolean.bfstack(table)
        for row in (0, 255, 256, 511):
            bits = [str((row >> i) & 1) for i in range(8, -1, -1)]
            assert run_bfstack(program, bits) == table[row]
        constant = boolean.bfstack(bit * 4096)
        stdin = esolangs.encode_inputs("BFStack", [1] * 12) + "0\n"
        assert esolangs.run("BFStack", constant + ",.", stdin=stdin) == bit + "0"

    @pytest.mark.medium
    def test_the_last_eight_input_row_does_not_wrap_to_zero(self) -> None:
        """Index 256 previously skipped the decoder's outer loop."""
        table = "0" * 255 + "1"
        assert run_bfstack(boolean.bfstack(table), ["1"] * 8) == "1"

    def test_encode_decode_structure(self) -> None:
        """The program encodes the inputs then tests the zero rows."""
        program = boolean.bfstack("0110")
        assert program.startswith(">>+,")  # result cell, accumulator, first input
        assert program.count(",") == 2  # one read per input
        assert program.endswith("+" * 48 + ".")  # print 48 + result

    def test_the_program_is_only_bfstack_commands(self) -> None:
        """No character outside the eight commands is emitted.

        BFStack ignores anything it does not recognise, the brainfuck
        convention, so a stray character is a *no-op* rather than an error:
        splicing one beside a ``[`` leaves the program computing exactly
        the same table.  That makes every behavioural check blind to it,
        and the alphabet the only thing that is not.
        """
        for table in ("10", "0110", "0001", "11111110"):
            assert set(boolean.bfstack(table)) <= set("+,-.<>[]"), table
