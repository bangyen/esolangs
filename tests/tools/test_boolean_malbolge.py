"""Malbolge's boolean generator: a source stub per row, no initializer.

The construction is the full 59049-cell store.  These tests run the shipped
programs through the repository interpreter, which is the execution gate: the
mixer, the re-encipherment-compensated data layout and the answer stubs are
only known to agree because every row is run.
"""

from __future__ import annotations

import hashlib
from itertools import product

import pytest

from esolangs import tools as boolean
from esolangs.exceptions import GeneratorCapError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.malbolge import run


def _rows(table: str) -> list[str]:
    """Return the program's output for every row, in table order."""
    n = len(table).bit_length() - 1
    program = boolean.malbolge(table)
    outputs = []
    for value in range(1 << n):
        bits = [(value >> (n - 1 - i)) & 1 for i in range(n)]
        io = ScriptedIO("".join(f"{bit}\n" for bit in bits))
        run(program, io)
        outputs.append(io.getvalue())
    return outputs


def _dense(n: int) -> str:
    """The suite's dense shape, rebuilt here so the module stands alone."""
    digest = hashlib.sha256(f"dense:{n}".encode()).digest()
    bits: list[str] = []
    block = 0
    while len(bits) < 2**n:
        digest = hashlib.sha256(digest + bytes([block & 255])).digest()
        bits.extend(str(byte & 1) for byte in digest)
        block += 1
    return "".join(bits[: 2**n])


def _parity(n: int) -> str:
    return "".join(str(row.bit_count() & 1) for row in range(2**n))


@pytest.mark.parametrize(
    ("n", "table"),
    [
        (n, table)
        for n in (1, 2, 3)
        for table in ("".join(bits) for bits in product("01", repeat=2**n))
    ],
)
def test_every_table_up_to_three_inputs(n: int, table: str) -> None:
    """The whole domain through n=3, run row by row."""
    assert _rows(table) == list(table)


@pytest.mark.slow
@pytest.mark.parametrize("n", (6, 9))
@pytest.mark.parametrize("shape", (_dense, _parity))
def test_dense_and_parity_run(n: int, shape: object) -> None:
    """The two worst-case shapes at the top of the supported range."""
    table = shape(n)  # type: ignore[operator]
    assert _rows(table) == list(table)


def test_program_is_the_full_store() -> None:
    """Every build is 59049 source characters, the whole address space."""
    assert len(boolean.malbolge("0110")) == 3**10


def test_ten_inputs_are_refused() -> None:
    """The mixer is injective with gap three only through nine inputs."""
    with pytest.raises(GeneratorCapError, match="at most 9 inputs"):
        boolean.malbolge(_dense(10))
