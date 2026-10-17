"""INTERCAL lays logical statements across valid token boundaries."""

import random

import pytest

import esolangs
from esolangs.generation.helpers import grid_width
from esolangs.generation.wrap import balance_score
from esolangs.languages.intercal.generator import (
    _intercal_tokens,
    _wrap_intercal,
    intercal,
)


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


def _fit_width_oracle(default: str) -> int:
    """Return the best side over every width a token run or row can fit."""
    maximum = grid_width(default) - 1
    widths = {1}
    for line in default.splitlines():
        if len(line) <= maximum:
            widths.add(len(line))
        tokens = _intercal_tokens(line)
        for start in range(len(tokens)):
            used = 0
            for token in tokens[start:]:
                used = used + 1 + len(token) if used else len(token)
                if used > maximum:
                    break
                widths.add(used)
    return min(
        balance_score(layout)[0]
        for layout in [default, *(_wrap_intercal(default, w) for w in widths)]
    )


@pytest.mark.parametrize("seed", range(12))
def test_balance_stays_within_five_percent_of_every_fit_width(seed: int) -> None:
    rng = random.Random(seed)
    for inputs in (1, 2, 3, 4, 5):
        table = format(rng.getrandbits(1 << inputs), f"0{1 << inputs}b")
        balanced = esolangs.generate("INTERCAL", table, balance=True)
        default = esolangs.generate("INTERCAL", table)
        assert balance_score(balanced)[0] <= 1.05 * _fit_width_oracle(default)
        for row, expected in enumerate(table):
            bits = list(map(int, format(row, f"0{inputs}b")))
            program = esolangs.instantiate(
                "INTERCAL", balanced, bits, truth_table=table
            )
            answer = esolangs.run("INTERCAL", program)
            assert esolangs.read_answer("INTERCAL", answer) == expected
