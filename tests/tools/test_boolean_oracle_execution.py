"""The retained Polynomial construction must compute its measured tables."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.polynomial import _Machine as Polynomial
from esolangs.tools.polynomial import _polynomial_assemble
from tests.tools.boolean_oracles import _polynomial_tree


@pytest.mark.medium
@pytest.mark.parametrize(
    "table",
    [format(v, f"0{2**n}b") for n in (1, 2, 3) for v in range(2 ** (2**n))],
)
def test_retired_oracle_executes_every_row(table: str) -> None:
    n = len(table).bit_length() - 1
    code = _polynomial_assemble(_polynomial_tree(table))
    for row, expected in enumerate(table):
        bits = format(row, f"0{n}b")
        io = ScriptedIO("".join(bits) + "Z\n")
        machine = Polynomial(code, io)
        for _ in range(1000):
            if machine.halted:
                break
            machine.step()
        assert machine.halted, (table, bits)
        assert io.getvalue() == expected, (table, bits)
        assert io.input_str() == "Z", (table, bits, "input count")
