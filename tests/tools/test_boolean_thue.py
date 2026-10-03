"""Thue source layout and emitted-size contracts."""

import pytest

from esolangs import tools as boolean
from esolangs.tools.thue import thue


@pytest.mark.parametrize("width", [1, 7, 8, 9, 10, 13, 40])
def test_narrow_sources_respect_width_floor(width: int) -> None:
    for value in range(256):
        table = f"{value:08b}"
        floor = max(map(len, thue(table, 1).splitlines()))
        assert max(map(len, thue(table, width).splitlines())) <= max(width, floor)


def test_layout_never_widens_the_natural_source() -> None:
    for n in range(1, 9):
        table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
        natural = max(map(len, thue(table).splitlines()))
        for width in range(1, natural + 2):
            assert max(map(len, thue(table, width).splitlines())) <= natural
    for table in ("01", "0110", "01101001"):
        plain = thue(table)
        natural = max(map(len, plain.splitlines()))
        for width in (natural, natural + 1):
            assert thue(table, width) == plain
        for width in range(1, natural):
            assert max(map(len, thue(table, width).splitlines())) <= max(width, 9)


def test_expansion_crosses_name_widths_without_widening() -> None:
    for n in (4, 6, 8):
        table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
        for width in (1, 13, 40, 80):
            program = thue(table, width)
            if width < len(table) + 3:
                assert max(map(len, program.splitlines())) < len(table) + 3


def test_chunk_bounds_stay_narrower_across_marker_digit_boundaries() -> None:
    """Expansion needs T>=8; its bound max(width,9,3d+3) is below T+3."""
    for n, floor in ((3, 7), (6, 9), (11, 12)):
        table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
        natural = max(map(len, thue(table).splitlines()))
        assert max(map(len, thue(table, 1).splitlines())) == floor
        for width in (1, natural - 1):
            assert max(map(len, thue(table, width).splitlines())) < natural


def test_thue_proof_text_counts_the_emitted_rules() -> None:
    """The ledger says nineteen fixed rules; the program carries nineteen."""
    import esolangs

    lines = boolean.thue("0110").splitlines()
    assert len(lines[: lines.index("::=")]) == 19
    scaling = esolangs.describe("Thue")["proof_status"]["scaling"]
    assert "nineteen fixed rules" in scaling


def test_thue_spells_the_table_once_and_its_rules_are_fixed() -> None:
    """Its emission is the table plus a constant: ``T + 187`` characters.

    ``T + 199`` before the line read became the marker itself: the rules
    ``0::=P`` and ``1::=Q`` only renamed it, so every three-input table
    sheds twelve characters, 52,992 to 49,920 over all 256.
    """
    sizes = [len(boolean.thue("01" * (2 ** (n - 1)))) for n in (1, 2, 3, 4)]
    assert sizes == [2**n + 187 for n in (1, 2, 3, 4)]
    total = sum(len(boolean.thue(f"{value:08b}")) for value in range(256))
    assert total == 49920


def test_short_tree_layout_and_source_size():
    for n in (1, 2):
        for value in range(1 << (1 << n)):
            assert max(map(len, thue(f"{value:0{1 << n}b}", 1).splitlines())) == 7
    assert len(thue("0110", 1)) == 90
