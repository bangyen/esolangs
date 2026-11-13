"""Tests for the 1 + i Boolean generator."""

from fractions import Fraction
from unittest.mock import patch

import esolangs
from esolangs.generation.algebraic import parity_bias
from esolangs.languages.one_i import generator
from esolangs.languages.one_i import interpreter as native
from esolangs.languages.one_i.tests.formulas import workspace_witness
from scripts.benchmark import WrittenState
from scripts.docs.resource_evidence import resource_bounds
from tests.support import generator_support as checks
from tests.support.event_io import ReadFirstIO
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        if table == "00":
            _check_constants()
            _check_arithmetic_tails()
        checks.assert_every_row("1 + i", table)


def _check_constants() -> None:
    for n, bit, _options, program in checks.constant_programs("1 + i", range(1, 13)):
        for row in ("0" * n, "1" * n):
            io = ReadFirstIO(
                esolangs.encode_inputs("1 + i", [int(b) for b in row]) + "7\n",
                expected=n,
            )
            checks.assert_constant_output(native.run, program, io, bit, n)
            assert io.input_num() == 7


def _check_arithmetic_tails() -> None:
    assert generator._parity_reader("0", [], 2) is None
    assert generator.parity_bias is parity_bias
    with patch.object(
        generator,
        "parity_bias",
        side_effect=lambda table: (
            None if (bias := parity_bias(table)) is None else 1 - bias
        ),
    ) as corrupted:
        assert checks.evaluate_generated("1 + i", "01101001") == "10010110"
        assert corrupted.called

    bounds = resource_bounds("1 + i")
    execution = bounds["execution"].formula
    workspace = bounds["workspace"].formula
    tables = [f"{v:04b}" for v in range(16)]
    tables += [
        "".join(str(row.bit_count() % 2) for row in range(1 << n)) for n in (3, 7, 8)
    ]
    tables += [
        "".join(str((row & mask).bit_count() % 2) for row in range(1 << n))
        for n, mask in ((6, 32), (8, 129))
    ]
    tables += [
        "".join(
            str(int(bool(row & a) and (bool(row & b) != invert)))
            for row in range(1 << n)
        )
        for n, a, b, invert in ((4, 8, 2, False), (5, 16, 2, True))
    ]
    tables += [workspace_witness(n) for n in range(2, 10)]
    for table in tables:
        n = len(table).bit_length() - 1
        program = esolangs.generate("1 + i", table).source
        for row in (0, (1 << n) // 3, 1 << (n - 1), (1 << n) - 1):
            io = ReadFirstIO(
                esolangs.encode_inputs("1 + i", list(map(int, f"{row:0{n}b}"))) + "7\n",
                expected=n,
            )
            machine = native._Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            steps = 0
            while not machine.halted:
                machine.step()
                written.sample(machine.workspace_snapshot())
                steps += 1
                for value in machine.values:
                    assert isinstance(value, native._Fn) or (
                        isinstance(value, tuple)
                        and all(isinstance(part, Fraction) for part in value)
                    )
            assert io.getvalue() == table[row]
            assert io.past_end == 0
            assert io.input_num() == 7
            assert steps <= execution(n, program)
            assert written.bits <= workspace(n, program)
