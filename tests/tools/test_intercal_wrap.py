"""INTERCAL lays logical statements across valid token boundaries."""

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
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.other.intercal import _Machine

    lines = _Machine(
        esolangs.instantiate("INTERCAL", template, [0] * inputs), ScriptedIO("")
    ).lines
    polite = sum(line.startswith("PLEASE ") for line in lines)
    assert len(lines) <= 5 * polite
    assert len(lines) >= 3 * polite


def test_intercal_width_splits_an_overwide_expression() -> None:
    table = "01101001"
    assert max(map(len, intercal(table, 1).splitlines())) < max(
        map(len, intercal(table).splitlines())
    )
    assert intercal(table, 1000) == intercal(table)


def test_intercal_xor_floor_and_narrow_corpus_size() -> None:
    assert max(map(len, intercal("0110", 1).splitlines())) == 6
    assert sum(len(intercal(format(value, "08b"), 1)) for value in range(256)) == 98588


def test_intercal_fitting_primitive_layout_keeps_its_source() -> None:
    from esolangs.tools.intercal import _intercal_narrow

    table = "01101001"
    previous = _intercal_narrow(table, simplify=False)
    width = max(map(len, previous.splitlines()))
    assert intercal(table, width) == previous


@pytest.mark.parametrize("width", [1, 6, 9, 17, 19, 20, 22, 40, 80])
@pytest.mark.parametrize("as_string", [False, True])
def test_intercal_split_operations_keep_public_provenance(
    width: int, *, as_string: bool
) -> None:
    table = "0110"
    template = esolangs.generate("INTERCAL", table, width)
    if as_string:
        template = str(template)
    shapes = set()
    for row, expected in enumerate(table):
        bits = list(map(int, format(row, "02b")))
        program = esolangs.instantiate("INTERCAL", template, bits, truth_table=table)
        shapes.add(tuple(map(len, program.splitlines())))
        assert (
            esolangs.read_answer("INTERCAL", esolangs.run("INTERCAL", program))
            == expected
        )
    assert len(shapes) == 1
    with pytest.raises(esolangs.TemplateError, match="is not the template"):
        esolangs.instantiate("INTERCAL", template, [0, 1], truth_table="1001")
