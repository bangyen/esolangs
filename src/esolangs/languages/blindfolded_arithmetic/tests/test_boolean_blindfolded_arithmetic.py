"""Tests for the Blindfolded Arithmetic Boolean generator."""

import pytest

import esolangs
from tests.support.generator_support import assert_every_row, measure_run
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    assert_every_row("Blindfolded Arithmetic", table)


def test_the_input_is_the_row_number() -> None:
    """The input must be positive, so row 0 is fed as 1."""
    assert esolangs.describe("Blindfolded Arithmetic")["input_shape"] == "row_number"
    assert esolangs.encode_inputs("Blindfolded Arithmetic", [0, 0]) == "1\n"
    assert esolangs.encode_inputs("Blindfolded Arithmetic", [1, 0]) == "3\n"
    _check_alternating_rounds()
    from esolangs.vm import make_vm

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                source = esolangs.generate(
                    "Blindfolded Arithmetic", bit * (1 << n), **options
                )
                assert len(source.replace("\n", "")) == 11
                for row in (0, 1, (1 << n) - 1):
                    vm = make_vm("Blindfolded Arithmetic", source, stdin=f"{row + 1}\n")
                    steps, state = measure_run(vm)
                    assert vm.output == bit
                    assert steps == 2
                    assert state.bits <= n + 8


def _check_alternating_rounds() -> None:
    from esolangs.languages.blindfolded_arithmetic.generator import _lookup
    from esolangs.languages.blindfolded_arithmetic.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

    # Both counter parities, ignored positions and complemented/mirrored answers.
    for table in (
        "0110",
        "01101001",
        "01011010",
        "00000001",
        "11111110",
        "0110100110010110",
        "1001011001101001",
    ):
        program = esolangs.generate("Blindfolded Arithmetic", table)
        for row, bit in enumerate(table):
            io = ScriptedIO(f"{row + 1} 99")
            machine = _Machine(program, io)
            for _ in range(program.count(";") + 1):
                machine.step()
            assert machine.halted
            assert machine.state[1] == len(machine.program) - 1
            assert io.getvalue() == bit
            assert io.reads == 1
            assert io.input_num() == 99
    assert _lookup(3, [0, 2]).count("c=a+a") == 1
