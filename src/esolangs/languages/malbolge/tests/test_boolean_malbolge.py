"""Malbolge's boolean generator: a source cell per row pair, no initializer."""

from __future__ import annotations

import random
from collections.abc import Sequence

import pytest

import esolangs
from esolangs.exceptions import GeneratorCapError
from esolangs.languages.malbolge import generator as boolean
from esolangs.languages.malbolge.generator import digits as _digits
from esolangs.languages.malbolge.generator import symmetric as _symmetric
from esolangs.languages.malbolge.generator.core import _table_char
from esolangs.languages.malbolge.generator.isa import _first_free, _g
from esolangs.languages.malbolge.interpreter import _XLAT1, _initial_memory, run
from esolangs.languages.malbolge.tests.navigation_checks import check_navigation
from esolangs.runtime.io import ScriptedIO
from scripts.docs.evidence import construction_boundaries
from tests.support.witness_tables import dense, row_bits


class _ReadFirstIO(ScriptedIO):
    def __init__(self, stdin: str, inputs: int) -> None:
        super().__init__(stdin)
        self.inputs = inputs

    def _write(self, value: object) -> None:
        if str(value).strip():
            assert self.reads == self.inputs
        super()._write(value)


def _rows(table: str, rows: Sequence[int] | None = None) -> list[str]:
    """Run the requested rows, requiring every input and leaving the sentinel."""
    n = len(table).bit_length() - 1
    program = boolean.malbolge(table)
    outputs = []
    for value in range(1 << n) if rows is None else rows:
        bits = row_bits(value, n)
        io = _ReadFirstIO("".join(f"{bit}" for bit in bits) + "Q", n)
        run(program, io)
        assert io.reads == n, (n, value, io.reads)
        assert io.input_char() == ord("Q"), (n, value)
        outputs.append(io.getvalue())
    return outputs


@pytest.mark.medium
# Wrapping depends on the width and the program length, not the table: the
# one-char floor, a stride, and one wider than most lines.
@pytest.mark.parametrize("width", [1, 13, 200])
@pytest.mark.parametrize("table", ["0110", dense(5)])
def test_wrapping_preserves_loaded_addresses_and_output(table: str, width: int) -> None:
    plain = boolean.malbolge(table)
    wrapped = esolangs.generate("Malbolge", table, width=width).source
    assert max(map(len, wrapped.splitlines())) <= width
    assert wrapped.replace("\n", "") == plain
    assert len(wrapped) == len(plain) + (len(plain) - 1) // width
    assert _initial_memory(wrapped) == _initial_memory(plain)
    n = len(table).bit_length() - 1
    rows = range(len(table)) if n <= 3 else (0, 1, len(table) // 2, len(table) - 1)
    for row in rows:
        io = ScriptedIO(f"{row:0{n}b}")
        run(wrapped, io)
        assert io.getvalue() == table[row]
        assert io.reads == n


@pytest.mark.slow
def test_ten_inputs_execute_every_row() -> None:
    """Execute every row of a dense ten-input table."""
    table = dense(10)
    assert _rows(table) == list(table)


@pytest.mark.parametrize(("n", "size"), [(14, 19683), (15, 52480), (16, 3**10)])
def test_program_size_from_fourteen_inputs(n: int, size: int) -> None:
    """Fourteen and fifteen end at their top live cell; sixteen is the store."""
    assert len(boolean.malbolge("01" * 2 ** (n - 1))) == size


@pytest.mark.parametrize("n", [1, 4, 13, 14, 15])
def test_short_builds_execute(n: int) -> None:
    """The short layout answers the first, last and middle rows of a random table."""
    table = format(random.Random(n).getrandbits(1 << n), f"0{1 << n}b")
    rows = sorted(
        {0, 1, 2, (1 << n) // 2, (1 << n) - 2, (1 << n) - 1} & set(range(1 << n))
    )
    assert _rows(table, rows) == [table[row] for row in rows]


@pytest.mark.parametrize("n", [1, 5, 13, 14, 15])
def test_short_builds_end_at_their_highest_live_cell(n: int) -> None:
    """Up to fifteen inputs the source ends at its highest live cell."""
    build = _digits._digits(n)
    live = max(*build.code, *build.data, *build.tables)
    assert build.words == live + 1 < 3**10
    assert len(boolean.malbolge("01" * 2 ** (n - 1))) == build.words


@pytest.mark.parametrize("n", [14, 15])
def test_hub_cells_pair_under_the_all_one_reswap(n: int) -> None:
    """Seeds without 0 trits let ``p`` under all-1 re-swap the hub cells.
    n=14 hubs at 19,687 read 0 on alternate pointers; random rows 28/29 missed stubs.
    """
    layout = _digits._short_layout(n)
    for seed in _digits._seed_values(layout).values():
        assert _digits._crazy(29524, seed) == _digits._s01(seed)


@pytest.mark.parametrize("n", [1, 4, 11])
def test_tables_differ_in_one_cell_per_row_pair(n: int) -> None:
    """Each nonconstant row pair owns one answer cell."""
    direct = boolean.malbolge("01" * 2 ** (n - 1))
    flipped = boolean.malbolge("10" * 2 ** (n - 1))
    assert sum(a != b for a, b in zip(direct, flipped, strict=True)) == 2 ** (n - 1)


def test_digit_readouts_are_distinct_and_clear_of_the_code() -> None:
    """Every row pair owns a cell in 6562..59040, above the code, no wrap."""
    cells = _digits._readouts_cells()
    assert len(set(cells)) == len(cells) == 2**15
    assert (min(cells), max(cells)) == (6562, 59040)
    lengths = {_digits._digits(n).words for n in range(1, 14)}
    (length,) = lengths
    assert 13114 <= length < 3**10
    readouts = [h - 1 for h in _digits._readouts_cells()]
    for k in range(5):
        values = {(s // 9**k) % 9 for s in readouts}
        assert len(values) == 8
    assert 0 not in {s // 9**4 for s in readouts}
    for n in range(1, 17):
        held = [_digits._held(n, group) for group in range(5)]
        assert sum(held) == 16 - n
        assert held == sorted(held)
        assert sum(0 < h < 3 for h in held) <= 1
    weights = _symmetric._s_readouts()
    assert len(weights) == 20480
    assert (min(weights), max(weights)) == (6565, 59040)
    assert sorted(set(weights.values())) == list(range(17))


@pytest.mark.medium
@pytest.mark.parametrize("n", range(1, 16))
def test_lower_arities_reuse_sixteens_cells(n: int) -> None:
    """Held reads make each arity's cells a subset of sixteen's."""
    cells = set(_digits._digits(n)[2])
    assert len(cells) == 2 ** (n - 1)
    assert cells <= set(_digits._readouts_cells())


@pytest.mark.medium
@pytest.mark.parametrize("n", [15, 16])
def test_digit_builds_label_every_cell(n: int) -> None:
    """Each table cell's residue admits the four single-cell answers."""
    _, _, tables, labels, _ = _digits._digits(n)
    for h in tables:
        for label in "01xn":
            _table_char(h, label, labels)
    _, _, _, labels, _ = _digits._digits(16)
    for h in range(94):
        for label in "01xn":
            _table_char(h, label, labels)


@pytest.mark.weekly
@pytest.mark.cost_evidence(
    "fifteen/sixteen-input digit readout samples both halves of answer pairs"
)
@pytest.mark.parametrize("n", [15, 16])
def test_digit_builds_sampled(n: int) -> None:
    """Every 128th row, offset per arity so both halves of each pair run."""
    table = dense(n)
    rows = range(n - 15, 2**n, 128)
    assert {table[2 * (row // 2) : 2 * (row // 2) + 2] for row in rows} == {
        "00",
        "01",
        "10",
        "11",
    }
    assert _rows(table, rows) == [table[row] for row in rows]


def test_unrestricted_digit_cap_executes_sixteen_inputs() -> None:
    """Seventeen dense inputs need 65,536 answer cells in a 59,049-cell store."""
    admitted, refused = construction_boundaries("Malbolge")["unrestricted_digit_cap"]
    table = admitted.table()
    rows = (0, 1, len(table) // 2, len(table) - 1)
    assert _rows(table, rows) == [table[row] for row in rows]
    with pytest.raises(GeneratorCapError, match="does neither"):
        boolean.malbolge(refused.table())


@pytest.mark.medium
@pytest.mark.parametrize("bit", [0, 1, 5, 16])
def test_seventeen_ignoring_an_input_builds_and_executes(bit: int) -> None:
    """Drop last, next-last, middle and first inputs through their native gadgets.
    Boundary rows execute under both values of each ignored input.
    """
    base = dense(16)
    table = "".join(
        base[(r & ((1 << bit) - 1)) | ((r >> (bit + 1)) << bit)] for r in range(1 << 17)
    )
    rows = sorted({0, 1, 2, 65535, 65536, 2**17 - 2, 2**17 - 1})
    assert _rows(table, rows) == [table[row] for row in rows]


@pytest.mark.medium
def test_seventeen_weight_constant_builds_and_executes() -> None:
    """Execute parity and seeded classes at zero, single-bit, half/full boundaries
    and the two alternating rows, covering every folded input and the stub's.
    """
    classes = "010111111000001011"
    admitted, refused = construction_boundaries("Malbolge")[
        "conditional_seventeen_input_cap"
    ]
    tables = (
        admitted.table(),
        "".join(classes[row.bit_count()] for row in range(1 << admitted.arity)),
    )
    with pytest.raises(GeneratorCapError, match="at most 16 inputs"):
        boolean.malbolge(refused.table())
    rows = sorted(
        {0, 1, 2, (1 << 16) - 1, 1 << 16, 2**17 - 2, 2**17 - 1}
        | {1 << j for j in range(17)}
    )
    for table in tables:
        assert _rows(table, rows) == [table[row] for row in rows]


def test_symmetric_build_rejects_a_short_table() -> None:
    """Short tables cannot determine all seventeen-input weight classes."""
    assert _symmetric._symmetric_program("0110") is None
    assert not any(hasattr(_digits, name) for name in ("_ignored_bit", "_project"))
    assert not hasattr(_symmetric, "_weight_classes")


@pytest.mark.parametrize("query", ["constant", "projection", "weights"])
def test_analysis_fault_changes_output(
    query: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each shared query controls an executed answer, including both 17-bit builds."""
    if query == "constant":
        table = "00"
        monkeypatch.setattr(boolean, "constant_output", lambda _: "1")
    elif query == "projection":
        table = "0011" * (1 << 15)
        monkeypatch.setattr(_digits, "read_at", lambda *_: "1" * (1 << 16))
    else:
        table = "".join(str(row.bit_count() % 2) for row in range(1 << 17))
        monkeypatch.setattr(_symmetric, "symmetric_outputs", lambda *_: "1" * 18)
    assert _rows(table, [0]) != [table[0]]


def test_a_value_meaning_needs_sixteen_characters() -> None:
    """A 16-value set meets every residue's character set; see the proof."""
    indices = [_XLAT1.index(op) for op in "ji*p</vo"]
    witness = {11, 15, 17, 22, 24, 29, 31, 38, 44, 62, 64, 71, 76, 78, 85, 91}
    for h in range(94):
        assert witness & {(i - h) % 94 for i in indices}


@pytest.mark.parametrize("n", range(1, 17))
def test_boundary_rows_execute_at_every_arity(n: int) -> None:
    table = dense(n)
    rows = sorted({0, 1, 2**n - 2, 2**n - 1})
    assert _rows(table, rows) == [table[row] for row in rows]


@pytest.mark.medium
@pytest.mark.parametrize("n", range(1, 17))
def test_every_answer_label_executes_at_every_arity(n: int) -> None:
    """Repeated pairs reach every label's stubs; dense tables missed an overwritten
    ``n`` operand cell that failed n=14's last ``not x`` pair.
    """
    half = 2 ** (n - 1)
    rows = sorted({0, 1, half, half + 1, 2 * half - 2, 2 * half - 1} - {2 * half})
    for pair in ("00", "11", "01", "10"):
        table = pair * half
        assert _rows(table, rows) == [table[row] for row in rows]


@pytest.mark.medium
def test_first_free_matches_the_cell_scan() -> None:
    """The arithmetic progression equals the old first-fit scan over cells."""
    check_navigation()
    for value in range(33, 127):
        for lo, hi in ((34, 128), (128, 420), (150, 420)):
            for blocked in (frozenset(), frozenset(range(lo, lo + 94))):
                scan = next(
                    (a for a in range(lo, hi) if _g(a) == value and a not in blocked),
                    None,
                )
                if scan is None:
                    with pytest.raises(AssertionError):
                        _first_free(value, lo, hi, blocked)
                else:
                    assert _first_free(value, lo, hi, blocked) == scan


@pytest.mark.parametrize("n", range(1, 18))
@pytest.mark.parametrize("bit", "01")
def test_constants_read_every_input(n: int, bit: str) -> None:
    table = bit * (1 << n)
    program = boolean.malbolge(table)
    assert len(program) <= 639
    if n == 8:
        assert len(program) == (632 if bit == "0" else 625)
    assert _rows(table, [0, (1 << n) - 1, int(("01" * n)[:n], 2)]) == [bit] * 3


@pytest.mark.medium
@pytest.mark.parametrize("kind", ["parity", "all_pairs"])
def test_seventeen_last_ignored_input_is_still_consumed(kind: str) -> None:
    base = (
        "".join(str(row.bit_count() % 2) for row in range(1 << 16))
        if kind == "parity"
        else "00011011" * (1 << 13)
    )
    table = "".join(bit * 2 for bit in base)
    rows = (*range(16), 65535, 65536, 131070, 131071)
    assert _rows(table, rows) == [table[row] for row in rows]
