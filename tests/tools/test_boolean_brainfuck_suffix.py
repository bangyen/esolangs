"""Larger suffix words preserve Brainfuck's command and workspace bounds."""

import random

import pytest

from esolangs.tools.brainfuck import _bf_ordered
from esolangs.tools.brainfuck_binary import binary_bank, larger_suffix_bank
from esolangs.tools.helpers import essential_inputs
from tests.tools.test_boolean_brainfuck_binary import _execute


def _fixture(remaining, classes):
    rng = random.Random(15)
    words = []
    while len(words) < classes:
        word = "".join(rng.choice("01") for _ in range(1 << remaining))
        if word not in words and "0" in word and "1" in word:
            words.append(word)
    pattern = list(range(classes)) * 2
    rng.shuffle(pattern)
    core = "".join(words[i] for i in pattern)
    core_bits = len(core).bit_length() - 1
    return core * (1 << (16 - core_bits)), core_bits


def _header(table):
    kept = essential_inputs(table, 16)
    reads, pending = [], ""
    for i in range(16):
        if i in kept or i > kept[-1]:
            reads.append(pending + "," + "-" * 48)
            pending = ""
        else:
            reads.append("")
            pending += ","
    return ">>".join(reads)


@pytest.mark.medium
@pytest.mark.parametrize("start", range(0, 1024, 128))
def test_public_five_input_bank_executes_every_essential_row(start):
    table, core_bits = _fixture(5, 16)
    header = _header(table)
    built = larger_suffix_bank(table, 1148 - len(header) - 49)
    assert built is not None
    body, commands = built
    assert commands == 436
    program = header + body + "+" * 48 + "."
    assert len(program) == 8485
    assert _bf_ordered(table, tuple(range(16))) == program
    rows = [
        fill << core_bits | row
        for fill in (0, (1 << (16 - core_bits)) - 1)
        for row in range(start, start + 128)
    ]
    assert _execute(table, program, rows, 1148) <= 1011
    assert larger_suffix_bank(table, commands - 1) is None


@pytest.mark.medium
@pytest.mark.parametrize("start", range(0, 256, 64))
def test_three_input_high_marker_preserves_native_output(start):
    table, core_bits = _fixture(3, 16)
    header = _header(table)
    built = binary_bank(table, 100000, remaining=3)
    assert built is not None
    body, commands = built
    program = header + body + "+" * 48 + "."
    rows = [
        fill << core_bits | row
        for fill in (0, (1 << (16 - core_bits)) - 1)
        for row in range(start, start + 64)
    ]
    _execute(table, program, rows, len(header) + commands + 49)


@pytest.mark.parametrize("table", ["01", "0011", "0" * 64])
def test_non_default_bank_requires_eligible_repeated_states(table):
    assert larger_suffix_bank(table, 100000) is None


def test_an_ineligible_suffix_keeps_the_other_candidates():
    table, _ = _fixture(3, 16)
    assert binary_bank(table, 100000, remaining=0) is None
    assert binary_bank(table, 100000, remaining=15) is None
