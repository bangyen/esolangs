"""Retired constructions must compute the table they are used to measure."""

import pytest

from esolangs.languages.polynomial.generator import _polynomial_assemble
from esolangs.languages.polynomial.interpreter import _Machine as Polynomial
from esolangs.languages.polynomial.tests.polynomial_support import _polynomial_tree
from esolangs.runtime.io import ScriptedIO


# A constant, XOR, and majority (an if-block beside an else-block).
@pytest.mark.parametrize("table", ["11", "0110", "00010111"])
def test_retired_oracle_executes_every_row(table: str) -> None:
    n = len(table).bit_length() - 1
    code = _polynomial_assemble(_polynomial_tree(table))
    machine_type = Polynomial
    for row, expected in enumerate(table):
        bits = format(row, f"0{n}b")
        io = ScriptedIO("".join(bits) + "Z\n")
        machine = machine_type(code, io)
        for _ in range(1000):
            if machine.halted:
                break
            machine.step()
        assert machine.halted, (table, bits)
        assert io.getvalue() == expected, (table, bits)
        assert io.input_str() == "Z", (table, bits, "input count")
