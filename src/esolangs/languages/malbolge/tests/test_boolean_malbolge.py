"""Malbolge's boolean generator: a source cell per row pair, no initializer."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from esolangs import generate
from esolangs.exceptions import GeneratorCapError
from esolangs.languages import generators as boolean
from esolangs.languages.malbolge.generator import digits as _digits
from esolangs.languages.malbolge.generator.core import _table_char
from esolangs.languages.malbolge.interpreter import _XLAT1, _initial_memory, run
from esolangs.runtime.io import ScriptedIO
from tests.support.witness_tables import dense, row_bits


def _rows(table: str, rows: Sequence[int] | None = None) -> list[str]:
    """Return the program's output for ``rows`` (default: every row) in order."""
    n = len(table).bit_length() - 1
    program = boolean.malbolge(table)
    outputs = []
    for value in range(1 << n) if rows is None else rows:
        bits = row_bits(value, n)
        io = ScriptedIO("".join(f"{bit}" for bit in bits))
        run(program, io)
        outputs.append(io.getvalue())
    return outputs


@pytest.mark.medium
# Wrapping depends on the width and the program length, not the table: the
# one-char floor, a stride, and one wider than most lines.
@pytest.mark.parametrize("width", [1, 13, 200])
@pytest.mark.parametrize("table", ["0110", dense(5)])
def test_wrapping_preserves_loaded_addresses_and_output(table: str, width: int) -> None:
    plain = boolean.malbolge(table)
    wrapped = generate("Malbolge", table, width=width)
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


def test_program_is_the_full_store() -> None:
    """Every build is 59049 source characters, the whole address space."""
    assert len(boolean.malbolge("0110")) == 3**10


@pytest.mark.parametrize("n", [1, 4, 11])
def test_tables_differ_in_one_cell_per_row_pair(n: int) -> None:
    """Every row pair owns one answer cell; nothing else depends on the table."""
    zeros = boolean.malbolge("0" * 2**n)
    ones = boolean.malbolge("1" * 2**n)
    assert sum(a != b for a, b in zip(zeros, ones, strict=True)) == 2 ** (n - 1)


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


def test_held_reads_fill_groups_from_the_last() -> None:
    """``16 - n`` reads are held, three per group from the last, leading first."""
    for n in range(1, 17):
        held = [_digits._held(n, group) for group in range(5)]  # noqa: SLF001
        assert sum(held) == 16 - n
        assert held == sorted(held)
        assert sum(0 < h < 3 for h in held) <= 1


@pytest.mark.medium
@pytest.mark.parametrize("n", range(1, 16))
def test_lower_arities_reuse_sixteens_cells(n: int) -> None:
    """Held reads make each arity's cells a subset of sixteen's."""
    cells = set(_digits._digits(n)[2])  # noqa: SLF001
    assert len(cells) == 2 ** (n - 1)
    assert cells <= set(_digits._readouts_cells())  # noqa: SLF001


@pytest.mark.medium
@pytest.mark.parametrize("n", [15, 16])
def test_digit_builds_label_every_cell(n: int) -> None:
    """Each table cell's residue admits the four single-cell answers."""
    _, _, tables, labels = _digits._digits(n)  # noqa: SLF001
    for h in tables:
        for label in "01xn":
            _table_char(h, label, labels)


def test_label_rule_admits_every_label_at_every_residue() -> None:
    """The label rule covers all 94 residues, not only today's table cells."""
    _, _, _, labels = _digits._digits(16)  # noqa: SLF001
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


def test_past_sixteen_inputs_is_refused() -> None:
    """Seventeen would need 65,536 answer cells in a 59,049-cell store."""
    with pytest.raises(GeneratorCapError, match="at most 16 inputs"):
        boolean.malbolge(dense(17))


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
    """A table of one repeated pair puts every row on one label's stubs.

    Dense tables miss labels: an ``n`` operand cell overwritten by a working
    cell passed them but failed n=14's last ``not x`` pair.
    """
    half = 2 ** (n - 1)
    rows = sorted({0, 1, half, half + 1, 2 * half - 2, 2 * half - 1} - {2 * half})
    for pair in ("00", "11", "01", "10"):
        table = pair * half
        assert _rows(table, rows) == [table[row] for row in rows]


def test_first_free_matches_the_cell_scan() -> None:
    """The arithmetic progression equals the old first-fit scan over cells."""
    from esolangs.languages.malbolge.generator.isa import _first_free, _g

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
