"""Tests for the Parenthesys Boolean generator."""

import pytest

import esolangs
from esolangs.languages.parenthesys.interpreter import run
from esolangs.runtime.io import ScriptedIO
from scripts.docs.evidence import construction_boundaries
from tests.support.generator_support import assert_native_rows, assert_saved_rows
from tests.support.witness_tables import SMALL_TABLES as TABLES

#: n=5 and 6 take the packed route, whose bit test reads every position.
PACKED = ["0110100110010110" * 2, "00010111" * 8, "1" + "0" * 63, "0" * 63 + "1"]


@pytest.mark.parametrize(
    "table", [*TABLES, "00010111", "01101001", "11101000", *PACKED]
)
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""

    if table == "00":
        language = esolangs.Language("Parenthesys")
        witnesses = construction_boundaries(language.name)[
            "literal_to_packed_lookup_cutoff"
        ]
        for witness in witnesses:
            n, case = witness.arity, witness.table()
            artifact = language.generate(case)
            assert ("[ord|" in artifact.source) == (n == 4)
            assert_saved_rows(language, artifact, case, range(len(case)))

    program = esolangs.generate("Parenthesys", table).source
    assert_native_rows("Parenthesys", table, program, run, sentinel="Q", token=True)


@pytest.mark.parametrize("n", range(1, 13))
@pytest.mark.parametrize("bit", "01")
def test_constants_read_every_input_and_leave_the_next(n: int, bit: str) -> None:
    for row in sorted({0, (1 << n) // 3, (1 << n) - 1}):
        program = esolangs.generate("Parenthesys", bit * (1 << n)).source
        if n == 8:
            assert len(program) == 11
        io = ScriptedIO("\n".join(f"{row:0{n}b}") + "\n9\n")
        run(program, io)
        assert io.getvalue() == bit
        assert io.reads == n
        assert io.input_token() == "9"
