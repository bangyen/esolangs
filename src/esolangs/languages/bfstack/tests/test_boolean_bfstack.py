"""bfstack generator tests."""

import random

import pytest

import esolangs
from esolangs.languages import generators as boolean
from tests.generators.boolean_runners import _runner
from tests.support.generator_support import assert_an_ignored_input_costs

run_bfstack = _runner("bfstack")


class TestBfstack:
    @pytest.mark.medium
    @pytest.mark.parametrize("n", [7, 8, 9, 12])
    def test_byte_index_boundaries(self, n: int) -> None:
        """Eight-input blocks preserve the byte-0 row and high input bits."""
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
        assert len(program) < len(boolean.bfstack(other + dense)) - 300
        for row in range(0, 512, 3):
            bits = [str((row >> i) & 1) for i in range(8, -1, -1)]
            assert run_bfstack(program, bits) == table[row], row

    @pytest.mark.medium
    def test_the_last_eight_input_row_does_not_wrap_to_zero(self) -> None:
        """Index 256 previously skipped the decoder's outer loop."""
        table = "0" * 255 + "1"
        assert run_bfstack(boolean.bfstack(table), ["1"] * 8) == "1"

    @pytest.mark.medium
    @pytest.mark.parametrize("ones", range(4))
    def test_the_byte_zero_row_is_a_zero_row(self, ones: int) -> None:
        """An eight-input block starts at the smallest start whose byte-0 row is 0."""
        rng = random.Random(ones)
        body = [rng.choice("01") for _ in range(256)]
        body[0] = "1"
        for k in range(1, ones + 1):
            body[256 - k] = "1"
        body[255 - ones] = "0"
        table = "".join(body)
        program = boolean.bfstack(table)
        assert program.startswith(">>" + "+" * (ones + 1) + ",")
        for row in range(256):
            bits = [str((row >> i) & 1) for i in range(7, -1, -1)]
            assert run_bfstack(program, bits) == table[row], row

    def test_generated_structure_and_written_payload(self) -> None:
        """Program shape and the payload used by workspace proofs."""
        program = boolean.bfstack("1101")  # asymmetric: the weighted encoder
        assert program.startswith(">>+,")  # result cell, accumulator, first input
        assert program.count(",") == 2  # one read per input
        assert program.endswith("+" * 48 + ".")  # print 48 + result
        for table in ("10", "0110", "0001", "11111110"):
            assert set(boolean.bfstack(table)) <= set("+,-.<>[]"), table

        from esolangs.languages.bfstack.generator import LANGUAGE
        from esolangs.languages.bfstack.interpreter import _Machine
        from esolangs.runtime.io import ScriptedIO

        io = ScriptedIO("A")
        machine = _Machine(",.", io)
        machine.step()
        machine.step()
        assert machine.halted
        assert io.getvalue() == "A"
        state = machine.snapshot()
        assert state[-1] > 0
        assert LANGUAGE.payload is not None
        assert LANGUAGE.payload(state) == (*state[:3], 0)
        assert LANGUAGE.payload((*state[:-1], 100)) == LANGUAGE.payload(state)


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """``,<``."""
    assert_an_ignored_input_costs("BFStack", 6, 2)


@pytest.mark.parametrize("n", [1, 2, 3, 8])
@pytest.mark.parametrize("bit", "01")
def test_constant_leaf_preserves_shape_and_input_consumption(n: int, bit: str) -> None:
    """A constant needs only input discards and the printed literal."""
    if n == 1 and bit == "0":
        _check_constants()
    program = boolean.bfstack(bit * (1 << n))
    assert len(program) == 2 * n + 50 + int(bit)
    for row in range(1 << n):
        assert run_bfstack(program, list(format(row, f"0{n}b"))) == bit
    stdin = esolangs.encode_inputs("BFStack", [1] * n) + "0"
    assert esolangs.run("BFStack", program + ",.", stdin=stdin) == bit + "0"


def test_small_tables_do_not_grow_and_execute() -> None:
    """The n=3 total is 59,247 characters."""
    from esolangs.languages.bfstack.generator import _bfstack_small

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
    assert total == 59_247


def _check_constants() -> None:
    from esolangs.languages.bfstack.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    for n in range(1, 13):

        class ReadFirstIO(ScriptedIO):
            expected = n

            def _write(self, value):
                assert self.reads == self.expected
                super()._write(value)

        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("BFStack", bit * (1 << n), **options)
                if not options:
                    assert len(program.replace("\n", "")) == 2 * n + 50 + int(bit)
                peak = 0
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "BFStack", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "7")
                    machine = _Machine(program, io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                        assert steps < 1000
                    assert io.getvalue() == bit
                    assert io.past_end == 0
                    assert io.input_char() == ord("7")
                    if not options:
                        assert steps == 2 * n + 50 + int(bit)
                        assert (
                            written.bits
                            <= 6 + len(program).bit_length() + n.bit_length()
                        )
                        peak = max(peak, written.bits)
                if not options:
                    assert peak == 6 + len(program).bit_length() + n.bit_length()
