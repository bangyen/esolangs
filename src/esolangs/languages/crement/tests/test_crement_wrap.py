"""Crement narrows complete instructions with equivalent operand spellings."""

import random

import pytest

import esolangs
from esolangs.languages.crement.generator import crement
from tests.support.divergence import diverges
from tests.support.generator_support import source_shape


@pytest.mark.medium
def test_crement_width_narrows_the_widest_instruction() -> None:
    table = "01101001"
    assert max(map(len, crement(table, 1).splitlines())) < max(
        map(len, crement(table).splitlines())
    )
    assert crement(table, 80) == crement(table)

    # A constant final quarter leaves the four-digit targets near their callers.
    table = f"{random.Random(0).getrandbits(2048):02048b}"[:1536] + "0" * 512
    default = esolangs.generate("Crement", table)
    narrowed = esolangs.generate("Crement", table, width=9)
    assert source_shape(default.source) == (9106, 1012, 10)
    assert source_shape(narrowed.source) == (9103, 1012, 9)
    rows = {0, 1, 511, 512, 1023, 1024, 1535, 1536, 2047}
    rows.update(random.Random(1).sample(range(2048), 23))
    assert {table[row] for row in rows} == {"0", "1"}
    for row in sorted(rows):
        bits = [int(bit) for bit in f"{row:011b}"]
        for template in (default, narrowed):
            source = esolangs.instantiate("Crement", template, bits)
            assert diverges("Crement", source, "") is (table[row] == "1")
    restored = esolangs.load_program(
        "Crement", esolangs.dump_program("Crement", narrowed)
    )
    source = esolangs.instantiate("Crement", restored, [0] * 11, truth_table=table)
    assert diverges("Crement", source, "") is (table[0] == "1")


def test_crement_data_only_setters_survive_saved_template(monkeypatch) -> None:
    def unexpected_scan(*_args):
        raise AssertionError("structured layout rediscovered its slots")

    monkeypatch.setattr("esolangs.artifacts.runs", unexpected_scan)
    template = esolangs.generate("Crement", "0110", width=1)
    template = esolangs.load_program(
        "Crement", esolangs.dump_program("Crement", template)
    )
    balanced = esolangs.generate("Crement", "00110110", balance=True)
    assert balanced.spans is not None
    assert all(end - start == 6 for start, end in balanced.spans)
    assert max(map(len, template.source.splitlines())) == 2
    for row, expected in enumerate("0110"):
        source = esolangs.instantiate(
            "Crement", template, [row // 2, row % 2], truth_table="0110"
        )
        assert max(map(len, source.source.splitlines())) == 2
        assert diverges("Crement", source, "") is (expected == "1")


@pytest.mark.parametrize("width", [4, 6, 7, 8])
@pytest.mark.parametrize("table", ["0110", "00010111", "01101001" * 4])
def test_crement_saved_layouts_keep_exact_provenance(table: str, width: int) -> None:
    template = esolangs.generate("Crement", table, width=width)
    template = esolangs.load_program(
        "Crement", esolangs.dump_program("Crement", template)
    )
    bits = [0] * (len(table).bit_length() - 1)
    source = esolangs.instantiate("Crement", template, bits, truth_table=table)
    assert diverges("Crement", source, "") is (table[0] == "1")
    with pytest.raises(esolangs.TemplateError):
        esolangs.instantiate(
            "Crement",
            template,
            bits,
            truth_table=table.translate(str.maketrans("01", "10")),
        )
