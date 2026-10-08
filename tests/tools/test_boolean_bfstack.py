"""bfstack generator tests."""

import random

import pytest

import esolangs
from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_bfstack,
)


class TestBfstack:
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
    def test_a_block_ignoring_an_input_reads_it_once(self) -> None:
        """A subtree whose halves agree reads and pops, branching neither."""
        rng = random.Random(9)
        dense, other = ("".join(rng.choice("01") for _ in range(256)) for _ in "ab")
        # Nine inputs, all essential, but the second is ignored below a zero
        # first: that half is one seven-input block repeated.
        table = dense[:128] * 2 + dense
        program = boolean.bfstack(table)
        assert len(program) < len(boolean.bfstack(other + dense)) - 500
        for row in range(0, 512, 3):
            bits = [str((row >> i) & 1) for i in range(8, -1, -1)]
            assert run_bfstack(program, bits) == table[row], row

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
        """No character outside the eight commands is emitted."""
        for table in ("10", "0110", "0001", "11111110"):
            assert set(boolean.bfstack(table)) <= set("+,-.<>[]"), table
