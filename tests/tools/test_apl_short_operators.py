"""Short operator definitions retain exact binding and one printed result."""

import pytest

from esolangs import generate
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.algebraic_programming_language import _Machine


@pytest.mark.parametrize("table", ["00", "11", "0110", "0001", "10010110"])
@pytest.mark.parametrize("width", [1, 4, 5, 6, 9])
def test_operator_binding_reads_every_input_once(table: str, width: int) -> None:
    n = len(table).bit_length() - 1
    program = generate("Algebraic Programming Language", table, width=width)
    assert max(map(len, program.splitlines())) <= max(width, 5)
    for row, expected in enumerate(table):
        io = ScriptedIO("\n".join(format(row, f"0{n}b")))
        machine = _Machine(program, io)
        for _ in range(200):
            if machine.halted:
                break
            machine.step()
        assert machine.halted
        assert io.reads == n
        assert io.getvalue() == expected + "\n"


def test_xor_arithmetic_family_reaches_four_columns() -> None:
    import esolangs
    from esolangs.tools.algebraic_programming_language import (
        algebraic_programming_language,
    )

    program = generate("Algebraic Programming Language", "0110", width=1)
    assert max(map(len, program.splitlines())) == 4
    assert len(program) == 49
    for row, expected in enumerate("0110"):
        stdin = "\n".join(format(row, "02b"))
        for source in (program, str(program)):
            assert (
                esolangs.run("Algebraic Programming Language", source, stdin=stdin)
                == expected + "\n"
            )
    assert algebraic_programming_language("0110", 4) == program
    assert max(map(len, algebraic_programming_language("0110", 5).splitlines())) == 5
