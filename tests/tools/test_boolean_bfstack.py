"""bfstack generator tests."""

import random

import pytest

import esolangs
from esolangs import tools as boolean
from tests.support.generator_support import assert_an_ignored_input_costs
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
        if n <= 9:
            rows = range(1 << n)
        else:
            special = {0, 127, 128, 255, 256, 2047, 2048, 4095}
            special |= set(rng.sample(range(1 << n), 32))
            rows = sorted(special)
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
    def test_two_blocks_in_four_slots_are_written_once_each(self) -> None:
        """A classifier picks the block, so a block repeated in slots costs once."""
        rng = random.Random(4)
        a, b = ("".join(rng.choice("01") for _ in range(128)) for _ in "ab")
        table = a + a + a + b
        program = boolean.bfstack(table)
        # Writing a twice (the equal-halves fold leaves three blocks) is 1.5x.
        assert len(program) < 1.3 * (len(boolean.bfstack(a)) + len(boolean.bfstack(b)))
        for row in range(0, 512, 7):
            bits = [str((row >> i) & 1) for i in range(8, -1, -1)]
            assert run_bfstack(program, bits) == table[row], row

    @pytest.mark.medium
    def test_the_last_eight_input_row_does_not_wrap_to_zero(self) -> None:
        """Index 256 previously skipped the decoder's outer loop."""
        table = "0" * 255 + "1"
        assert run_bfstack(boolean.bfstack(table), ["1"] * 8) == "1"

    def test_encode_decode_structure(self) -> None:
        """The program encodes the inputs, tests the zero rows, and prints."""
        program = boolean.bfstack("0110")
        assert program.startswith(">>+,")  # result cell, accumulator, first input
        assert program.count(",") == 2  # one read per input
        assert program.endswith("+" * 48 + ".")  # print 48 + result
        for table in ("10", "0110", "0001", "11111110"):
            assert set(boolean.bfstack(table)) <= set("+,-.<>[]"), table


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """``,<``."""
    assert_an_ignored_input_costs("BFStack", 6, 2)


@pytest.mark.parametrize("n", range(1, 9))
@pytest.mark.parametrize("bit", "01")
def test_constant_leaf_is_used_at_every_arity(n: int, bit: str) -> None:
    """A constant needs only input discards and the printed literal."""
    program = boolean.bfstack(bit * (1 << n))
    assert len(program) == 2 * n + 51 + int(bit)
    for row in range(1 << n):
        assert run_bfstack(program, list(format(row, f"0{n}b"))) == bit
    stdin = esolangs.encode_inputs("BFStack", [1] * n) + "0"
    assert esolangs.run("BFStack", program + ",.", stdin=stdin) == bit + "0"


def test_small_tables_do_not_grow_and_execute() -> None:
    """The n=3 total drops from 58,948 to 58,934 characters."""
    from esolangs.tools.bfstack import _bfstack_small

    total = 0
    for n in range(1, 4):
        for value in range(1 << (1 << n)):
            table = format(value, f"0{1 << n}b")
            program = boolean.bfstack(table)
            assert len(program) <= len(_bfstack_small(table, n))
            if n == 3:
                total += len(program)
            for row, expected in enumerate(table):
                assert run_bfstack(program, list(format(row, f"0{n}b"))) == expected
    assert total == 58_934
