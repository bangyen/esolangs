"""Tests for the What!? Boolean generator."""

import random
from unittest.mock import patch

import pytest

import esolangs
from esolangs import run
from scripts.benchmark import WrittenState
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_every_row, evaluate_generated
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
        _check_copyless()
        from esolangs.languages.what import generator

        with patch.object(generator, "change_points", return_value=[]) as corrupted:
            assert evaluate_generated("What!?", "0011") == "1111"
            assert corrupted.called
    assert_every_row("What!?", table)


@pytest.mark.medium
def test_a_table_past_the_low_input_cap_labels_its_blocks() -> None:
    """n=16 splits into two labelled blocks; rows on both sides answer."""
    table = format(random.Random(1).getrandbits(1 << 16), "065536b")
    program = esolangs.generate("What!?", table).source
    for row in (0, 32767, 32768, 65535):
        stdin = esolangs.encode_inputs("What!?", [int(b) for b in format(row, "016b")])
        got = run("What!?", program, stdin=stdin, timeout=10).output
        assert esolangs.read_answer("What!?", got) == table[row], row


def _check_constants() -> None:
    from esolangs.languages.what.interpreter import _Machine

    for n in range(1, 17):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("What!?", bit * (1 << n), **options).source
                if not options:
                    assert len(program.replace("\n", "")) <= 3 * n + 2
                peak = 0
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "What!?", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "\n7\n", expected=n)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.workspace_snapshot())
                        steps += 1
                        assert steps < 1000
                    assert io.getvalue() == bit
                    assert io.past_end == 0
                    assert io.input_num() == 7
                    if not options:
                        assert steps == n + 2
                        assert (
                            written.bits
                            <= 256 + (n + 2).bit_length() + (2 * n - 1).bit_length()
                        )
                        peak = max(peak, written.bits)
                if not options:
                    assert peak == 256 + (n + 2).bit_length() + (2 * n - 1).bit_length()


def _check_copyless() -> None:
    from esolangs.languages.what.interpreter import _Machine

    total = 0
    for value in range(256):
        table = f"{value:08b}"
        program = esolangs.generate("What!?", table).source
        total += len(program)
        for row in range(8):
            stdin = esolangs.encode_inputs("What!?", list(map(int, f"{row:03b}")))

            io = ReadFirstIO(stdin + "\n7\n", expected=3)
            machine = _Machine(program, io)
            while not machine.halted:
                machine.step()
            assert io.getvalue() == table[row]
            assert io.past_end == 0
            assert io.input_num() == 7
    assert total == 12778
