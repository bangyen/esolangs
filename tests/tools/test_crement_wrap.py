"""Crement narrows complete instructions with equivalent operand spellings."""

import pytest

import esolangs
from esolangs.interpreters.other.crement import _parse
from esolangs.tools.crement import crement
from tests.divergence import diverges
from tests.tools.fills import instantiate_crement


@pytest.mark.parametrize("width", [1, 2, 3, 4, 5, 6, 7, 8, 11, 80, None])
@pytest.mark.parametrize(
    "table",
    ["01", "10", "0000", "1111", "0110", "00010111", "01101001" * 4, "0" * 63 + "1"],
)
def test_crement_narrow_operands_preserve_every_row(
    table: str, width: int | None
) -> None:
    template = esolangs.generate("Crement", table, width)
    plain = crement(table)
    floor = max(map(len, crement(table, 1).splitlines()))
    if width is None:
        assert template == plain
    else:
        assert max(map(len, template.splitlines())) <= max(width, floor)
    inputs = len(table).bit_length() - 1
    for row, expected in enumerate(table):
        bits = [int(bit) for bit in format(row, f"0{inputs}b")]
        source = instantiate_crement(template, bits)
        assert _parse(source) == _parse(instantiate_crement(plain, bits))
        assert diverges("Crement", source, "") is (expected == "1")


def test_crement_width_narrows_the_widest_instruction() -> None:
    table = "01101001"
    assert max(map(len, crement(table, 1).splitlines())) < max(
        map(len, crement(table).splitlines())
    )
    assert crement(table, 80) == crement(table)


def test_crement_data_only_setters_survive_plain_template() -> None:
    template = esolangs.generate("Crement", "0110", 1)
    assert max(map(len, template.splitlines())) == 2
    for row, expected in enumerate("0110"):
        source = esolangs.instantiate(
            "Crement", str(template), [row // 2, row % 2], truth_table="0110"
        )
        assert max(map(len, source.splitlines())) == 2
        assert diverges("Crement", source, "") is (expected == "1")


@pytest.mark.parametrize("width", [4, 6, 7, 8])
@pytest.mark.parametrize("table", ["0110", "00010111", "01101001" * 4])
def test_crement_saved_layouts_keep_exact_provenance(table: str, width: int) -> None:
    template = str(esolangs.generate("Crement", table, width))
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
