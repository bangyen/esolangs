"""Narrow Minifuck layouts preserve fresh walks and atomic input setters."""

import pytest

import esolangs
from esolangs.tools.helpers import TEMPLATE_CHAR, mark_runs
from esolangs.tools.minifuck import minifuck
from esolangs.tools.minifuck.sim import PAIR
from esolangs.tools.wrap import wrap_program


# Widths 1 and 3 build the same program.
@pytest.mark.parametrize("width", [1, 4, 11, 40, 80])
@pytest.mark.parametrize("plain", [False, True])
def test_minifuck_layout_and_post_fill_wrapper_preserve_provenance(
    width: int, *, plain: bool
) -> None:
    table = "0110"
    template = esolangs.generate("Minifuck", table, width=width)
    if plain:
        template = str(template)
    for row, expected in enumerate(table):
        bits = [row >> 1, row & 1]
        source = esolangs.instantiate(
            "Minifuck", template, bits, width=1, truth_table=table
        )
        assert esolangs.run("Minifuck", source) == expected
    with pytest.raises(esolangs.TemplateError, match="not the template"):
        esolangs.instantiate("Minifuck", template, [0, 0], width=1, truth_table="0001")


def test_minifuck_xor_floor_and_rendered_size_tradeoff() -> None:
    table = "0110"
    natural = mark_runs(minifuck(table), TEMPLATE_CHAR, (PAIR,) * 2)
    assert max(map(len, wrap_program(natural, "minifuck", 1).splitlines())) == 33
    assert (
        max(map(len, esolangs.generate("Minifuck", table, width=1).splitlines())) == 1
    )


def test_minifuck_parity_provenance_retains_skip_absorbing_linefeeds() -> None:
    template = str(esolangs.generate("Minifuck", "0110", width=1))
    with pytest.raises(esolangs.TemplateError, match="not the template"):
        esolangs.instantiate(
            "Minifuck", template.replace("[\n[", "[[", 1), [0, 1], truth_table="0110"
        )
