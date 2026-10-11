"""Affine accumulators keep parity in the output byte and discard other setters."""

import pytest

import esolangs
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from esolangs.tools.minifuck import _affine_mask, _parity_columns, minifuck_setters
from tests.tools.minifuck_support import _MinifuckCase


@pytest.mark.medium
@pytest.mark.parametrize("paired", [False, True])
def test_forced_accumulators_compute_every_small_affine_table(*, paired: bool) -> None:
    runner = _MinifuckCase()
    for n in range(6):
        for mask in range(1 << n):
            for bias in (0, 1):
                table = "".join(
                    str(((row & mask).bit_count() & 1) ^ bias) for row in range(1 << n)
                )
                assert _affine_mask(table) == mask
                template = _parity_columns(n, bias, mask=mask, paired=paired)
                pairs = minifuck_setters(template, n)
                assert len(set(pairs)) <= 1
                for row in range(1 << n):
                    bits = [row >> shift & 1 for shift in range(n - 1, -1, -1)]
                    source = fill_runs(template, TEMPLATE_CHAR, pairs, bits)
                    assert runner.run_minifuck(source) == table[row]


@pytest.mark.medium
@pytest.mark.parametrize("mask", [0, 1, 85, 255])
@pytest.mark.parametrize("bias", [0, 1])
def test_public_eight_input_affine_layouts_execute_every_row(
    mask: int, bias: int
) -> None:
    n = 8
    table = "".join(str(((row & mask).bit_count() & 1) ^ bias) for row in range(1 << n))
    for width, balance in ((None, False), (1, False), (4, False), (None, True)):
        template = esolangs.generate("Minifuck", table, width=width, balance=balance)
        if mask == 255 and bias == 0 and width is None and not balance:
            assert len(template) == 257
        for row, expected in enumerate(table):
            bits = [row >> shift & 1 for shift in range(n - 1, -1, -1)]
            source = esolangs.instantiate("Minifuck", template, bits)
            assert esolangs.run("Minifuck", source) == expected


def test_nonaffine_tables_decline_the_accumulator() -> None:
    assert _affine_mask("0001") is None
