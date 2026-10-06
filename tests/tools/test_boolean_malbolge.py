"""Malbolge's boolean generator: a source stub per row, no initializer."""

from __future__ import annotations

import hashlib
import importlib
from collections.abc import Sequence

import pytest

from esolangs import generate
from esolangs import tools as boolean
from esolangs.exceptions import GeneratorCapError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.malbolge import _XLAT1, _load, run
from esolangs.tools.malbolge.core import _cascade

_module = importlib.import_module("esolangs.tools.malbolge")


def _rows(table: str, rows: Sequence[int] | None = None) -> list[str]:
    """Return the program's output for ``rows`` (default: every row) in order."""
    n = len(table).bit_length() - 1
    program = boolean.malbolge(table)
    outputs = []
    for value in range(1 << n) if rows is None else rows:
        bits = [(value >> (n - 1 - i)) & 1 for i in range(n)]
        io = ScriptedIO("".join(f"{bit}" for bit in bits))
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


@pytest.mark.medium
@pytest.mark.parametrize("width", [1, 7, 13, 40, 80, 200])
@pytest.mark.parametrize("table", ["00", "11", "0110", "01101001", _dense(5)])
def test_wrapping_preserves_loaded_addresses_and_output(table: str, width: int) -> None:
    plain = boolean.malbolge(table)
    wrapped = generate("Malbolge", table, width)
    assert max(map(len, wrapped.splitlines())) <= width
    assert wrapped.replace("\n", "") == plain
    assert len(wrapped) == len(plain) + (len(plain) - 1) // width
    assert _load(wrapped) == _load(plain)
    n = len(table).bit_length() - 1
    rows = range(len(table)) if n <= 3 else (0, 1, len(table) // 2, len(table) - 1)
    for row in rows:
        io = ScriptedIO(f"{row:0{n}b}")
        run(wrapped, io)
        assert io.getvalue() == table[row]
        assert io.reads == n


#: How many items each ``every_row`` sweep is split into, per shape.
#:
#: A sweep is execution, not build: a thirteen-input row is 12.1ms of which
#: the load is 1%, so that shape alone is ~100s.  As one item per shape the
#: sweeps pinned one worker each while the constant shapes finished at once
#: and the rest idled, so the wall was the longest single item; split, the
#: work spreads and the wall falls to the total over the worker count.  The
#: thirteen-input sweep went 103.9s -> 56.9s on ten workers, and the whole
#: weekly band 103.5s -> 82.5s.  Rebuilding per part is free -- the build is
#: 0.17s, 0.2% of a sweep.  Strided rather than blocked so the parts cost the
#: same, and their union is still every row.
#:
#: Four is where the band bottoms out: eight parts measured 83.6s, no better,
#: because the remaining wall is the band's total work over the cores it has
#: rather than the longest item.  Raising this past the core count buys
#: nothing.
_SWEEP_PARTS = 4


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
    _, level, _, _ = _cascade()
    return [row for row, lvl in enumerate(level) if lvl == 1]


def test_cascade_leaves_128_pairs_to_the_second_decoder() -> None:
    """The first readout resolves 1792 rows; the second separates the rest."""
    assert len(_second_level_rows()) == 256


def test_eleven_input_tables_differ_in_one_cell_per_row() -> None:
    """Every row owns one answer cell; the rows a pair shares point at NEXT."""
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


_digits = importlib.import_module("esolangs.tools.malbolge.digits")


def test_digit_readouts_are_distinct_and_clear_of_the_code() -> None:
    """Every row pair owns a cell in 6562..59040, above the code, no wrap."""
    cells = _digits._readouts_cells()  # noqa: SLF001
    assert len(set(cells)) == len(cells) == 2**15
    assert (min(cells), max(cells)) == (6562, 59040)


def test_digit_readouts_hold_three_bits_per_digit() -> None:
    """Each two-trit digit takes eight values; the top one never ``(0, 0)``."""
    readouts = [h - 1 for h in _digits._readouts_cells()]  # noqa: SLF001
    for k in range(5):
        values = {(s // 9**k) % 9 for s in readouts}
        assert len(values) == 8
    assert 0 not in {s // 9**4 for s in readouts}


@pytest.mark.medium
def test_fifteen_inputs_reuse_sixteens_cells() -> None:
    """The constant read makes fifteen's cells a subset of sixteen's."""
    fifteen = set(_digits._digits(15)[2])  # noqa: SLF001
    assert len(fifteen) == 2**14
    assert fifteen <= set(_digits._readouts_cells())  # noqa: SLF001


@pytest.mark.medium
@pytest.mark.parametrize("n", [15, 16])
def test_digit_builds_label_every_cell(n: int) -> None:
    """Each table cell's residue admits the four single-cell answers."""
    _, _, tables, labels = _digits._digits(n)  # noqa: SLF001
    for h in tables:
        for label in "01xn":
            _module._table_char(h, label, labels)  # noqa: SLF001


@pytest.mark.slow
@pytest.mark.parametrize("n", [15, 16])
@pytest.mark.parametrize("shape", [_dense, _parity])
def test_digit_builds_sampled(n: int, shape: object) -> None:
    """Every 128th row, offset per arity so both halves of each pair run."""
    table = shape(n)  # type: ignore[operator]
    rows = range(n - 15, 2**n, 128)
    assert _rows(table, rows) == [table[row] for row in rows]


def test_past_sixteen_inputs_is_refused() -> None:
    """Seventeen would need 65,536 answer cells in a 59,049-cell store."""
    with pytest.raises(GeneratorCapError, match="at most 16 inputs"):
        boolean.malbolge(_dense(17))


def test_a_value_meaning_needs_sixteen_characters() -> None:
    """A 16-value set meets every residue's character set; see the proof."""
    indices = [_XLAT1.index(op) for op in "ji*p</vo"]
    witness = {11, 15, 17, 22, 24, 29, 31, 38, 44, 62, 64, 71, 76, 78, 85, 91}
    for h in range(94):
        assert witness & {(i - h) % 94 for i in indices}


@pytest.mark.parametrize("n", range(11, 17))
def test_public_high_arity_routes_execute_boundary_rows(n: int) -> None:
    table = _dense(n)
    rows = [0, 1, 2**n - 2, 2**n - 1]
    assert _rows(table, rows) == [table[row] for row in rows]


def test_fourteen_rejects_colliding_final_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_module, "_F_LEVEL3", (0, 0))
    with pytest.raises(AssertionError, match="a row never resolves"):
        _module._f_tables.__wrapped__()  # noqa: SLF001
