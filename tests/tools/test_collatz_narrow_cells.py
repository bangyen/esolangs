"""Executed Collatz Multiverse odd-index decoder layouts."""

import random

import pytest

import esolangs
from esolangs.tools.collatz_multiverse import _cm_layout, collatz_multiverse
from tests.generator_support import evaluate_generated
from tests.tools.boolean_runners import run_collatz_multiverse


@pytest.mark.medium
def test_every_small_narrow_table_executes_at_its_floor() -> None:
    for n in range(1, 4):
        size = 1 << n
        for value in range(1 << size):
            table = f"{value:0{size}b}"
            source = esolangs.generate("collatz-multiverse", table, 1)
            assert max(map(len, source.splitlines())) == 26
            for row, expected in enumerate(table):
                assert run_collatz_multiverse(source, list(f"{row:0{n}b}")) == expected
            assert _cm_layout(source, 1) == source


@pytest.mark.parametrize("width", [1, 25, 26, 27, 28, 29, 40])
def test_public_layout_reads_all_inputs_and_preserves_fitting_source(
    width: int,
) -> None:
    for table in ("00", "11", "01", "10", "0110", "0001", "10010110"):
        raw = collatz_multiverse(table)
        old_layout = _cm_layout(raw, width)
        source = esolangs.generate("collatz-multiverse", table, width)
        if max(map(len, old_layout.splitlines())) <= width:
            assert source == old_layout
        assert evaluate_generated("collatz-multiverse", table, width=width) == table


@pytest.mark.parametrize("n", [4, 6, 8, 10, 12])
def test_larger_narrow_address_weights_execute(n: int) -> None:
    rng = random.Random(7531 + n)
    table = "".join(str(rng.randrange(2)) for _ in range(1 << n))
    source = esolangs.generate("collatz-multiverse", table, 1)
    for row in {0, (1 << n) - 1, *(rng.randrange(1 << n) for _ in range(4))}:
        assert run_collatz_multiverse(source, list(f"{row:0{n}b}")) == table[row]


def test_alias_prefix_is_not_inserted_when_it_cannot_narrow() -> None:
    source = "a=zx+negativeOne,NOT PRINT.\na=zx+z,DO PRINT."
    narrowed = _cm_layout(source, 1)
    assert narrowed == source
    assert esolangs.run("collatz-multiverse", narrowed) == "\x00"


def test_xor_floor_and_numbered_constant_source_size() -> None:
    source = collatz_multiverse("0110", 1)
    assert max(map(len, source.splitlines())) == 26
    assert len(source) == 1269
    for table in ("00", "11"):
        assert max(map(len, collatz_multiverse(table, 1).splitlines())) == 26
