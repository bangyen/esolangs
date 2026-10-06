"""Boolfuck byte conventions and generated execution."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.boolfuck import run
from esolangs.tools.boolfuck import boolfuck
from tests.witness_tables import witnesses


@pytest.mark.parametrize(
    ("code", "stdin", "expected"),
    [
        ("+;", "", "\x01"),
        ("<+;>;<;", "", "\x05"),
        (",;" * 8, "A", "A"),
        (",;" * 8, "", "\x00"),
        ("+[,];", "", "\x00"),
        ("ignored text", "", ""),
    ],
)
def test_byte_conventions(code: str, stdin: str, expected: str) -> None:
    io = ScriptedIO(stdin)
    run(code, io)
    assert io.getvalue() == expected


@pytest.mark.parametrize("n", [1, 2, 3])
def test_all_three_input_tables(n: int) -> None:
    for table in witnesses(n):
        code = boolfuck(table)
        for row in range(1 << n):
            io = ScriptedIO(f"{row:0{n}b}")
            run(code, io)
            assert io.getvalue() == table[row]
