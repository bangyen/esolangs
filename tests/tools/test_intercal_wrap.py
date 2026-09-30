"""INTERCAL narrows expressions into complete polite calculation statements."""

import random

import pytest

import esolangs
from esolangs.tools.intercal import intercal


@pytest.mark.parametrize("inputs", [1, 2, 3, 4, 5, 6])
@pytest.mark.parametrize("width", [1, 20, 31, 40, 80, None])
def test_intercal_narrow_expressions_compute_every_row(
    inputs: int, width: int | None
) -> None:
    table = format(random.Random(inputs).getrandbits(1 << inputs), f"0{1 << inputs}b")
    template = esolangs.generate("INTERCAL", table, width)
    natural = intercal(table)
    floor = max(map(len, intercal(table, 1).splitlines()))
    assert template.count("@") == 2 * inputs
    if width is None:
        assert template == natural
    else:
        assert max(map(len, template.splitlines())) <= max(width, floor)
    lines = template.splitlines()
    polite = sum(line.startswith("PLEASE ") for line in lines)
    assert len(lines) <= 5 * polite
    assert len(lines) >= 3 * polite
    assert esolangs.evaluate("INTERCAL", table, width=width) == table


@pytest.mark.parametrize(
    "table", ["00", "11", "01", "10", "0000", "1111", "0110", "0001"]
)
def test_intercal_narrow_constant_and_shared_paths(table: str) -> None:
    assert esolangs.evaluate("INTERCAL", table, width=1) == table


def test_intercal_width_splits_an_overwide_expression() -> None:
    table = "01101001"
    assert max(map(len, intercal(table, 1).splitlines())) < max(
        map(len, intercal(table).splitlines())
    )
    assert intercal(table, 1000) == intercal(table)
