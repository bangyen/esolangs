"""Crement narrows complete instructions with equivalent operand spellings."""

import random

import pytest

import esolangs
from esolangs import compat
from esolangs.languages.crement.generator import crement
from tests.support.divergence import diverges


@pytest.mark.medium
def test_crement_width_narrows_the_widest_instruction() -> None:
    table = "01101001"
    assert max(map(len, crement(table, 1).splitlines())) < max(
        map(len, crement(table).splitlines())
    )
    assert crement(table, 80) == crement(table)

    # A constant final quarter leaves the four-digit targets near their callers.
    table = f"{random.Random(0).getrandbits(2048):02048b}"[:1536] + "0" * 512
    default = compat.generate("Crement", table)
    narrowed = compat.generate("Crement", table, width=9)
    assert (
        len(default),
        len(default.splitlines()),
        max(map(len, default.splitlines())),
    ) == (9106, 1012, 10)
    assert (
        len(narrowed),
        len(narrowed.splitlines()),
        max(map(len, narrowed.splitlines())),
    ) == (9103, 1012, 9)
    rows = {0, 1, 511, 512, 1023, 1024, 1535, 1536, 2047}
    rows.update(random.Random(1).sample(range(2048), 23))
    assert {table[row] for row in rows} == {"0", "1"}
    for row in sorted(rows):
        bits = [int(bit) for bit in f"{row:011b}"]
        for template in (default, narrowed):
            source = compat.instantiate("Crement", template, bits)
            assert diverges("Crement", source, "") is (table[row] == "1")
    source = compat.instantiate("Crement", str(narrowed), [0] * 11, truth_table=table)
    assert diverges("Crement", source, "") is (table[0] == "1")


def test_crement_data_only_setters_survive_plain_template() -> None:
    template = compat.generate("Crement", "0110", width=1)
    assert max(map(len, template.splitlines())) == 2
    for row, expected in enumerate("0110"):
        source = compat.instantiate(
            "Crement", str(template), [row // 2, row % 2], truth_table="0110"
        )
        assert max(map(len, source.splitlines())) == 2
        assert diverges("Crement", source, "") is (expected == "1")


@pytest.mark.parametrize("width", [4, 6, 7, 8])
@pytest.mark.parametrize("table", ["0110", "00010111", "01101001" * 4])
def test_crement_saved_layouts_keep_exact_provenance(table: str, width: int) -> None:
    template = str(compat.generate("Crement", table, width=width))
    bits = [0] * (len(table).bit_length() - 1)
    source = compat.instantiate("Crement", template, bits, truth_table=table)
    assert diverges("Crement", source, "") is (table[0] == "1")
    with pytest.raises(esolangs.TemplateError):
        compat.instantiate(
            "Crement",
            template,
            bits,
            truth_table=table.translate(str.maketrans("01", "10")),
        )
