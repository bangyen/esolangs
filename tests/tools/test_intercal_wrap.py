"""INTERCAL lays logical statements across valid token boundaries."""

import pytest

import esolangs
from esolangs.tools.intercal import intercal
from tests.generator_support import evaluate_generated


def test_intercal_width_splits_an_overwide_expression() -> None:
    table = "01101001"
    assert max(map(len, intercal(table, 1).splitlines())) < max(
        map(len, intercal(table).splitlines())
    )
    assert intercal(table, 1000) == intercal(table)


def test_intercal_xor_floor_and_narrow_corpus_size() -> None:
    assert max(map(len, intercal("0110", 1).splitlines())) == 6
    assert sum(len(intercal(format(value, "08b"), 1)) for value in range(256)) == 91053


def test_intercal_fitting_primitive_layout_keeps_its_source() -> None:
    from esolangs.tools.intercal import _intercal_narrow

    table = "01101001"
    previous = _intercal_narrow(table, simplify=False)
    width = max(map(len, previous.splitlines()))
    assert intercal(table, width) == previous
    assert evaluate_generated("INTERCAL", table, width=width) == table


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


@pytest.mark.parametrize("operator", ["&", "V", "?"])
def test_intercal_split_intermediates_fit_onespots(operator: str) -> None:
    from esolangs.interpreters.other.intercal import _expression

    for left in (0, 1):
        for right in (0, 1):
            # The raw mingle fits a onespot; a unary on it can set bit31
            # (right rotation, manual s3.4.3), so it applies after storing.
            value, end = _expression("'.1$.2'", {1: left, 2: right})
            intermediate, _bits = value
            assert end == 7
            assert 0 <= intermediate <= 3
            answer, _end = _expression(f"'.{operator}3~#1'", {3: intermediate})
            expected = (
                left & right
                if operator == "&"
                else left | right
                if operator == "V"
                else left ^ right
            )
            assert answer[0] == expected
