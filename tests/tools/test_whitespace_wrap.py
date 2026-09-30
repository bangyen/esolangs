"""Whitespace folds only through complete commands and binary Horner pushes."""

import random

import pytest

import esolangs
from esolangs.tools.whitespace import _ADD, _DISCARD, _END, _OUT_NUM, _push, whitespace


@pytest.mark.parametrize("inputs", [1, 2, 3, 4, 5, 6])
@pytest.mark.parametrize("width", [1, 7, 8, 11, 27, 80, None])
def test_whitespace_horner_chunks_compute_every_row(
    inputs: int, width: int | None
) -> None:
    table = format(random.Random(inputs).getrandbits(1 << inputs), f"0{1 << inputs}b")
    source = esolangs.generate("Whitespace", table, width)
    if width is None:
        assert source == whitespace(table)
    else:
        assert max(map(len, source.split("\n"))) <= max(7, width)
    assert esolangs.evaluate("Whitespace", table, width=width) == table


@pytest.mark.parametrize(
    "table", ["00", "11", "01", "10", "0000", "1111", "0" * 31 + "1"]
)
def test_whitespace_chunks_preserve_zero_and_high_bits(table: str) -> None:
    assert esolangs.evaluate("Whitespace", table, width=7) == table


def test_whitespace_separator_preserves_a_live_stack() -> None:
    prefix = _push(19) + _push(23)
    ending = _ADD + _OUT_NUM + _END
    assert esolangs.run("Whitespace", prefix + ending) == "42"
    assert esolangs.run("Whitespace", prefix + _push(0) + _DISCARD + ending) == "42"


def test_whitespace_keeps_fitting_source_and_narrows_a_long_literal() -> None:
    table = "01101001" * 8
    natural = whitespace(table)
    assert whitespace(table, 1000) == natural
    assert max(map(len, whitespace(table, 7).split("\n"))) < max(
        map(len, natural.split("\n"))
    )
