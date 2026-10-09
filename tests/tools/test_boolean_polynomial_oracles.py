"""Retired constructions must compute the table they are used to measure."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.polynomial import _Machine as Polynomial
from esolangs.tools.polynomial import _polynomial_assemble
from tests.tools.polynomial_support import _polynomial_tree


@pytest.mark.parametrize("oracle", ["polynomial_tree"])
# A constant, XOR, and majority (an if-block beside an else-block).
@pytest.mark.parametrize("table", ["11", "0110", "00010111"])
def test_retired_oracle_executes_every_row(oracle: str, table: str) -> None:
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
        assert machine.halted, (oracle, table, bits)
        assert io.getvalue() == expected, (oracle, table, bits)
        assert io.input_str() == "Z", (oracle, table, bits, "input count")
