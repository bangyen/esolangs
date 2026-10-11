"""Packed selection preserves rank order and executes the same FRACTRAN source."""

import itertools
import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fractran import _Machine
from esolangs.tools.fractran import PAIR
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from tests.proofs import _fractran_order
from tests.proofs._fractran_bit_order import BitAvailable
from tests.proofs._fractran_order import _Available, capacity, stream_template
from tests.support.witness_tables import row_bits


def test_packed_selector_realizes_every_small_permutation() -> None:
    for size in range(1, 7):
        for order in itertools.permutations(range(size)):
            available = list(range(size))
            packed = BitAvailable(size)
            for symbol in order:
                rank = available.index(symbol)
                assert packed.pop(rank) == available.pop(rank)
            assert not any(packed.cells)
            assert not any(packed.widths)


@pytest.mark.medium
def test_packed_selector_bit_access_controls() -> None:
    for size in (1, 3, 64, 255, 256, 1024, 4096):
        for mode in ("first", "last-digit", "seeded-digit"):
            packed = BitAvailable(size)
            reference = _Available(size)
            rng = random.Random(20261007)
            for remaining in range(size, 0, -1):
                bound = 1 << (remaining.bit_length() - 1)
                rank = (
                    0
                    if mode == "first"
                    else bound - 1
                    if mode == "last-digit"
                    else rng.randrange(bound)
                )
                assert packed.pop(rank) == reference.pop(rank)
            flips = sum(2 * (i & -i) - 1 for i in range(1, size + 1))
            assert packed.reads["decrement"] == flips
            assert packed.writes["decrement"] == flips
            assert not any(packed.cells)
            assert not any(packed.widths)
            assert packed.storage_bits == sum(
                (i & -i).bit_length() for i in range(1, size + 1)
            )
            if size & (size - 1) == 0:
                depth = size.bit_length() - 1
                assert packed.locations == size * (3 * depth + 6) // 2
            if mode == "first":
                assert packed.reads["compare"] == packed.reads["subtract"] == 0
                assert packed.writes["subtract"] == 0
            elif size == 4096 and mode == "seeded-digit":
                assert packed.reads["compare"] == 47872
                assert packed.reads["subtract"] == 287704
                assert packed.writes["subtract"] == 121645


@pytest.mark.medium
def test_packed_selector_preserves_executed_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rng = random.Random(20261007)
    for n in (0, 1, 2, 4, 6, 8):
        size = 1 << n
        k = 2
        while capacity(k) < size:
            k += 1
        for table in (
            "0" * size,
            "1" * size,
            "".join(str(rng.randrange(2)) for _ in range(size)),
        ):
            monkeypatch.setattr(_fractran_order, "_Available", _Available)
            reference = stream_template(table, k)
            monkeypatch.setattr(_fractran_order, "_Available", BitAvailable)
            packed = stream_template(table, k)
            assert packed == reference
            for row in sorted({0, size // 3, size - 1}):
                bits = row_bits(row, n)
                source = fill_runs(packed, TEMPLATE_CHAR, [PAIR] * n, bits)
                io = ScriptedIO("")
                machine = _Machine(source, io)
                for _ in range(200 * k + 100):
                    if machine.halted:
                        break
                    machine.step()
                else:
                    pytest.fail("packed-selector stream exceeded control budget")
                assert io.getvalue().strip() == str(1 + int(table[row]))
