"""Tests for the Blindfolded Arithmetic Boolean generator."""

from unittest.mock import patch

import esolangs
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import make_vm
from scripts.docs.evidence import construction_boundaries
from tests.support.analysis_support import assert_analysis_complement
from tests.support.generator_support import (
    assert_every_row,
    assert_saved_rows,
    measure_run,
)
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        assert_every_row("Blindfolded Arithmetic", table)


def test_the_input_is_the_row_number() -> None:
    """The input must be positive, so row 0 is fed as 1."""
    from esolangs.languages.blindfolded_arithmetic import generator as boolean

    language = esolangs.Language("Blindfolded Arithmetic")
    for witness in construction_boundaries(language.name)[
        "parity_integer_arity_cutoff"
    ]:
        n, table = witness.arity, witness.table()
        with patch.object(
            boolean, "_parity_integer", wraps=boolean._parity_integer
        ) as parity:
            artifact = language.generate(table)
        assert parity.call_count == int(n == 4)
        assert_saved_rows(language, artifact, table, range(len(table)))

    assert esolangs.describe("Blindfolded Arithmetic")["input_shape"] == "row_number"
    assert esolangs.encode_inputs("Blindfolded Arithmetic", [0, 0]) == "1\n"
    assert esolangs.encode_inputs("Blindfolded Arithmetic", [1, 0]) == "3\n"
    assert_analysis_complement("Blindfolded Arithmetic", "read_at")
    _check_alternating_rounds()
    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                source = esolangs.generate(
                    "Blindfolded Arithmetic", bit * (1 << n), **options
                ).source
                assert len(source.replace("\n", "")) == 11
                for row in (0, 1, (1 << n) - 1):
                    vm = make_vm("Blindfolded Arithmetic", source, stdin=f"{row + 1}\n")
                    steps, state = measure_run(vm)
                    assert vm.output == bit
                    assert steps == 2
                    assert state.bits <= n + 8


def _check_alternating_rounds() -> None:
    from esolangs.languages.blindfolded_arithmetic.interpreter import _Machine

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
        program = esolangs.generate("Blindfolded Arithmetic", table).source
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
