"""Boolfuck byte conventions and generated execution."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.boolfuck import run
from esolangs.tools.boolfuck import boolfuck


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


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.parametrize("batch", range(4))
def test_all_three_input_tables(n: int, batch: int) -> None:
    total = 1 << (1 << n)
    for value in range(batch * total // 4, (batch + 1) * total // 4):
        table = f"{value:0{1 << n}b}"
        code = boolfuck(table)
        for row in range(1 << n):
            io = ScriptedIO(f"{row:0{n}b}")
            run(code, io)
            assert io.getvalue() == table[row]
