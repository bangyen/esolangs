"""Malbolge's boolean generator: a source stub per row, no initializer.

The construction is the full 59049-cell store.  These tests run the shipped
programs through the repository interpreter, which is the execution gate: the
mixer, the re-encipherment-compensated data layout and the answer stubs are
only known to agree because every row is run.  Eleven inputs go through the
pointer cascade; its 256 second-level rows are always among the rows run.
"""

from __future__ import annotations

import hashlib
import importlib
from collections.abc import Sequence
from itertools import product

import pytest

from esolangs import tools as boolean
from esolangs.exceptions import GeneratorCapError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.malbolge import run

_module = importlib.import_module("esolangs.tools.malbolge")


def _rows(table: str, rows: Sequence[int] | None = None) -> list[str]:
    """Return the program's output for ``rows`` (default: every row) in order."""
    n = len(table).bit_length() - 1
    program = boolean.malbolge(table)
    outputs = []
    for value in range(1 << n) if rows is None else rows:
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
    "table",
    ["".join(bits) for n in (1, 2, 3) for bits in product("01", repeat=2**n)],
)
def test_every_table_up_to_three_inputs(table: str) -> None:
    """The whole domain through n=3, run row by row."""
    assert _rows(table) == list(table)


@pytest.mark.slow
@pytest.mark.parametrize("n", [6, 9, 10])
@pytest.mark.parametrize("shape", [_dense, _parity])
def test_dense_and_parity_run(n: int, shape: object) -> None:
    """The two worst-case shapes at the top of the supported range."""
    table = shape(n)  # type: ignore[operator]
    assert _rows(table) == list(table)


def test_program_is_the_full_store() -> None:
    """Every build is 59049 source characters, the whole address space."""
    assert len(boolean.malbolge("0110")) == 3**10


def _second_level_rows() -> list[int]:
    _, level, _, _ = _module._cascade()  # noqa: SLF001
    return [row for row, lvl in enumerate(level) if lvl == 1]


def test_cascade_leaves_128_pairs_to_the_second_decoder() -> None:
    """The first readout resolves 1792 rows; the second separates the rest."""
    assert len(_second_level_rows()) == 256


def test_eleven_input_tables_differ_in_one_cell_per_row() -> None:
    """Every row owns one answer cell; the rows a pair shares point at NEXT.

    The all-0 and all-1 tables therefore differ in exactly 2048 of the 59049
    cells: one per resolved row at level 1, one per row at level 2.
    """
    zeros = boolean.malbolge("0" * 2**11)
    ones = boolean.malbolge("1" * 2**11)
    assert len(zeros) == len(ones) == 3**10
    assert sum(a != b for a, b in zip(zeros, ones, strict=True)) == 2**11


@pytest.mark.slow
@pytest.mark.parametrize("shape", [_dense, _parity])
def test_eleven_inputs_sampled(shape: object) -> None:
    """Every eighth row and every second-level row of the two shapes."""
    table = shape(11)  # type: ignore[operator]
    rows = sorted({*range(0, 2**11, 8), *_second_level_rows()})
    assert _rows(table, rows) == [table[row] for row in rows]


@pytest.mark.slow
@pytest.mark.weekly
@pytest.mark.parametrize("shape", [_dense, _parity])
def test_eleven_inputs_every_row(shape: object) -> None:
    """The full 2048-row sweep, the cascade's execution gate."""
    table = shape(11)  # type: ignore[operator]
    assert _rows(table) == list(table)


def _wide_second_level_rows() -> list[int]:
    _, level, _, _ = _module._wide()  # noqa: SLF001
    return [2 * row + x for x in (0, 1) for row, lvl in enumerate(level[x]) if lvl]


def test_twelve_inputs_split_the_last_off_the_cascade() -> None:
    """560 of 4096 rows collide at level 1; both halves reach the decoder."""
    rows = _wide_second_level_rows()
    assert len(rows) == 560
    assert {row & 1 for row in rows} == {0, 1}


@pytest.mark.slow
@pytest.mark.parametrize("shape", [_dense, _parity])
def test_twelve_inputs_sampled(shape: object) -> None:
    """Every sixteenth row and every second-level row of the two shapes."""
    table = shape(12)  # type: ignore[operator]
    rows = sorted({*range(0, 2**12, 16), *_wide_second_level_rows()})
    assert _rows(table, rows) == [table[row] for row in rows]


@pytest.mark.slow
@pytest.mark.weekly
@pytest.mark.parametrize("shape", [_dense, _parity])
def test_twelve_inputs_every_row(shape: object) -> None:
    """The full 4096-row sweep, the selector's execution gate."""
    table = shape(12)  # type: ignore[operator]
    assert _rows(table) == list(table)


def _thirteen_second_level_rows() -> list[int]:
    _, _, level, _, _ = _module._thirteen()  # noqa: SLF001
    return [
        4 * row + 2 * x + last
        for x in (0, 1)
        for row, lvl in enumerate(level[x])
        if lvl
        for last in (0, 1)
    ]


def test_thirteen_inputs_label_every_residue() -> None:
    """Each table cell's residue admits all five single-cell labels."""
    _, _, level, tables, labels = _module._thirteen()  # noqa: SLF001
    for x in (0, 1):
        for row, h in enumerate(tables[0][x]):
            wanted = "N01xn" if level[x][row] else "01xn"
            for label in wanted:
                _module._table_char(h, label, labels)  # noqa: SLF001


@pytest.mark.slow
@pytest.mark.parametrize("shape", [_dense, _parity])
def test_thirteen_inputs_sampled(shape: object) -> None:
    """Every thirty-second row and every second-level row of the two shapes."""
    table = shape(13)  # type: ignore[operator]
    rows = sorted({*range(0, 2**13, 32), *_thirteen_second_level_rows()})
    assert _rows(table, rows) == [table[row] for row in rows]


@pytest.mark.slow
@pytest.mark.weekly
@pytest.mark.parametrize(
    "shape", [_dense, _parity, lambda n: "0" * 2**n, lambda n: "1" * 2**n]
)
def test_thirteen_inputs_every_row(shape: object) -> None:
    """The full 8192-row sweep, the four-answer labels' execution gate."""
    table = shape(13)  # type: ignore[operator]
    assert _rows(table) == list(table)


def _fourteen_rows(levels: set[int]) -> list[int]:
    """Rows of the fourteen-input table whose copy resolves at one of ``levels``."""
    _, _, level, _, _ = _module._fourteen()  # noqa: SLF001
    return [
        8 * row + 2 * copy + last
        for copy in range(4)
        for row, lvl in enumerate(level[copy])
        if lvl in levels
        for last in (0, 1)
    ]


def test_fourteen_inputs_resolve_in_three_levels() -> None:
    """7,427 copies own their level-1 cell; 685 resolve at level 2, 80 at 3."""
    _, _, level, _, _ = _module._fourteen()  # noqa: SLF001
    counts = [sum(lvl == k for per_copy in level for lvl in per_copy) for k in range(3)]
    assert counts == [7427, 685, 80]


def test_fourteen_inputs_level_three_has_its_own_region() -> None:
    """Level-3 cells sit in 13122..19682; levels 1 and 2 at 19683 or above."""
    _, _, level, tables, _ = _module._fourteen()  # noqa: SLF001
    for copy in range(4):
        for row, k in enumerate(level[copy]):
            for lvl in range(k + 1):
                h = tables[lvl][copy][row]
                assert 13122 < h < 19683 if lvl == 2 else h > 19683


def test_fourteen_inputs_label_every_residue() -> None:
    """Each cell a copy reads admits N and the four single-cell answers."""
    _, _, level, tables, labels = _module._fourteen()  # noqa: SLF001
    for copy in range(4):
        for row, k in enumerate(level[copy]):
            for lvl in range(k + 1):
                h = tables[lvl][copy][row]
                for label in "N01xn":
                    _module._table_char(h, label, labels)  # noqa: SLF001


def test_fourteen_inputs_second_pass_is_nine_nops_and_a_jump() -> None:
    """The decoder's cells, once run, decode to nops and then an ``i``."""
    start = _module._F_DECODER  # noqa: SLF001
    cells = ((start, "j"), (start + 1, "j"))
    second = [_module._second_pass(op, a) for a, op in cells]  # noqa: SLF001
    second += [_module._second_pass("o", start + 2 + k) for k in range(8)]  # noqa: SLF001
    assert second == ["o"] * 9 + ["i"]


@pytest.mark.slow
@pytest.mark.parametrize("shape", [_dense, _parity])
def test_fourteen_inputs_sampled(shape: object) -> None:
    """Every 64th row, every level-3 row and every fourth level-2 row."""
    table = shape(14)  # type: ignore[operator]
    rows = sorted(
        {*range(0, 2**14, 64), *_fourteen_rows({2}), *_fourteen_rows({1})[::4]}
    )
    assert _rows(table, rows) == [table[row] for row in rows]


@pytest.mark.slow
@pytest.mark.weekly
@pytest.mark.parametrize(
    "shape", [_dense, _parity, lambda n: "0" * 2**n, lambda n: "1" * 2**n]
)
def test_fourteen_inputs_every_row(shape: object) -> None:
    """The full 16,384-row sweep, the three-level cascade's execution gate."""
    table = shape(14)  # type: ignore[operator]
    assert _rows(table) == list(table)


@pytest.mark.parametrize("n", [15, 16])
def test_past_fourteen_inputs_is_refused(n: int) -> None:
    """Fifteen would need eight copies and a fourth level."""
    with pytest.raises(GeneratorCapError, match="at most 14 inputs"):
        boolean.malbolge(_dense(n))
