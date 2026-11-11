"""bfstack generator tests."""

import random
from unittest.mock import patch

import pytest

import esolangs
from esolangs import run
from esolangs.languages.bfstack import generator as boolean
from esolangs.languages.bfstack.generator import _bfstack_small
from esolangs.registry._certification import load as load_certification
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.generators.boolean_runners import _runner
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import (
    assert_an_ignored_input_costs,
    constant_programs,
)

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
        assert run("BFStack", constant + ",.", stdin=stdin).output == bit + "0"

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

        rng = random.Random(9)
        dense = "".join(rng.choice("01") for _ in range(512))
        # Nine essential inputs exceed one byte block; the tenth is ignored.
        # Both halves still need branching, reaching the recursive discard.
        table = dense * 2
        program = boolean.bfstack(table)
        assert program.startswith(",<")
        for row in range(1024):
            bits = list(f"{row:010b}")
            stdin = esolangs.encode_inputs("BFStack", list(map(int, bits))) + "7"
            assert (
                run("BFStack", program + ",.", stdin=stdin).output == table[row] + "7"
            )

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
        if ones == 0:
            with patch.object(boolean, "_start", return_value=0) as corrupted:
                broken = boolean.bfstack(table)
                assert run_bfstack(broken, ["0"] * 8) == "0"
                assert corrupted.called
        program = boolean.bfstack(table)
        assert program.startswith(">>" + "+" * (ones + 1) + ",")
        for row in range(256):
            bits = [str((row >> i) & 1) for i in range(7, -1, -1)]
            assert run_bfstack(program, bits) == table[row], row

    def test_generated_structure_and_written_payload(self) -> None:
        """Program shape and the payload used by workspace proofs."""
        assert_analysis_complement("BFStack", "symmetric_weights", "01101001")
        assert_analysis_complement("BFStack", "input_weights", "00010011")
        """Program shape and the payload used by workspace proofs."""
        program = boolean.bfstack("1101")  # asymmetric: the weighted encoder
        assert program.startswith(">>+,")  # result cell, accumulator, first input
        assert program.count(",") == 2  # one read per input
        assert program.endswith("+" * 48 + ".")  # print 48 + result
        for table in ("10", "0110", "0001", "11111110"):
            assert set(boolean.bfstack(table)) <= set("+,-.<>[]"), table

        from esolangs.languages.bfstack.descriptor import LANGUAGE
        from esolangs.languages.bfstack.interpreter import _Machine

        io = ScriptedIO("A")
        machine = _Machine(",.", io)
        machine.step()
        machine.step()
        assert machine.halted
        assert io.getvalue() == "A"
        state = machine.snapshot()
        assert state[-1] > 0
        assert load_certification(LANGUAGE).payload is not None
        assert load_certification(LANGUAGE).payload(state) == (*state[:3], 0)
        assert load_certification(LANGUAGE).payload(
            (*state[:-1], 100)
        ) == load_certification(LANGUAGE).payload(state)


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
        _check_identities()
    if n == 8 and bit == "1":
        with pytest.raises(StopIteration):
            boolean._start("1" * 256)
        assert boolean._start("1" * 255 + "0") == 1
    program = boolean.bfstack(bit * (1 << n))
    assert len(program) == 2 * n + 50 + int(bit)
    for row in range(1 << n):
        assert run_bfstack(program, list(format(row, f"0{n}b"))) == bit
    stdin = esolangs.encode_inputs("BFStack", [1] * n) + "0"
    assert run("BFStack", program + ",.", stdin=stdin).output == bit + "0"


def test_small_tables_do_not_grow_and_execute() -> None:
    """The n=3 total is 58,899 characters."""
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
    assert total == 58_899


def _check_identities() -> None:
    from esolangs.languages.bfstack.interpreter import _Machine
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("BFStack")["workspace"].formula
    execution = resource_bounds("BFStack")["execution"].formula

    for n in range(1, 13):
        for selected in range(n):
            table = "".join(
                str((row >> (n - selected - 1)) & 1) for row in range(1 << n)
            )
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("BFStack", table, **options).source
                assert len(program.replace("\n", "")) == 2 * n
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    bits = f"{row:0{n}b}"
                    io = ScriptedIO(bits + "Q")
                    machine = _Machine(program, io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = 0
                    while not machine.halted:
                        if program[machine.ind] == ".":
                            assert io.reads == n
                        machine.step()
                        written.sample(machine.workspace_snapshot())
                        steps += 1
                        assert steps < 100
                    assert io.getvalue() == bits[selected]
                    assert io.past_end == 0
                    assert io.input_char() == ord("Q")
                    if not options:
                        assert steps == 2 * n
                        assert (
                            written.bits
                            <= 12 + n.bit_length() + len(program).bit_length()
                        )
    rng = random.Random(2026110209)
    identity = "01" * 128
    dense = "".join(rng.choice("01") for _ in range(256))
    for table in (identity + dense, dense + identity):
        program = boolean.bfstack(table)
        for row in (0, 1, 255, 256, 511):
            io = ScriptedIO(f"{row:09b}" + "Q")
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            steps = 0
            while not machine.halted:
                if program[machine.ind] == ".":
                    assert io.reads == 9
                machine.step()
                written.sample(machine.workspace_snapshot())
                steps += 1
                assert steps <= execution(9, program)
            assert io.getvalue() == table[row]
            assert io.reads == 9
            assert io.input_char() == ord("Q")
            assert written.bits <= workspace(9, program)


def _check_constants() -> None:
    from esolangs.languages.bfstack.interpreter import _Machine

    for n, bit, options, program in constant_programs("BFStack", range(1, 13)):
        if not options:
            assert len(program.replace("\n", "")) == 2 * n + 50 + int(bit)
        peak = 0
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            stdin = esolangs.encode_inputs("BFStack", list(map(int, f"{row:0{n}b}")))
            io = ReadFirstIO(stdin + "7", expected=n)
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            steps = count_steps(machine, 999, written=written)
            assert io.getvalue() == bit
            assert io.past_end == 0
            assert io.input_char() == ord("7")
            if not options:
                assert steps == 2 * n + 50 + int(bit)
                assert written.bits <= 6 + len(program).bit_length() + n.bit_length()
                peak = max(peak, written.bits)
        if not options:
            assert peak == 6 + len(program).bit_length() + n.bit_length()
