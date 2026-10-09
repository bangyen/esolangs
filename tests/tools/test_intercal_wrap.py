"""INTERCAL lays logical statements across valid token boundaries."""

import pytest

import esolangs
from esolangs.tools.intercal import intercal


def test_intercal_token_floor_and_wrapped_corpus_size() -> None:
    assert max(map(len, intercal("0110", 1).splitlines())) == 6
    assert sum(len(intercal(format(value, "08b"), 1)) for value in range(256)) == 98704


@pytest.mark.parametrize("width", [1, 6, 9, 17, 22, 40])
@pytest.mark.parametrize("as_string", [False, True])
def test_intercal_wrapped_template_keeps_public_provenance(
    width: int, *, as_string: bool
) -> None:
    table = "0110"
    template = esolangs.generate("INTERCAL", table, width=width)
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
