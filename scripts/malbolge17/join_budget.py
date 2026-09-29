"""Measure the current address and decoder maps against the 17-input table."""

from __future__ import annotations

import itertools

from address17 import ALL2, group_word
from address_gadget import build as build_address
from decoder_group import _build as build_decoder
from decoder_group import _setup as setup_decoder

from esolangs.interpreters.other.malbolge import _crazy, _op
from esolangs.tools._malbolge_core import _WORDS


def main() -> None:
    """Report exact occupied-cell counts for the current separate emitters."""
    address_cells: set[int] = set()
    source, _, _, count = build_address(
        z=None, dispatch_ab=True, parity=True, occupied=address_cells
    )
    address_cells.update(range(10, 18))  # startup precedes the emitted parts
    assert len(address_cells) == count
    decoder = build_decoder(0, setup_decoder())
    decoder_cells = set(decoder.code)
    table = {
        _crazy(ALL2 - 2 + offset, group_word(list(bits))) + 1
        for bits in itertools.product(range(2), repeat=14)
        for offset in range(3)
    }
    assert len(table) == 49_152
    overlap = address_cells & decoder_cells
    conflicts = {
        cell for cell in overlap if _op(ord(source[cell]), cell) != decoder.code[cell]
    }
    union = address_cells | decoder_cells
    print(
        f"address {len(address_cells)}, decoder {len(decoder_cells)}, "
        f"raw union {len(union)}, conflicting overlap {len(conflicts)}"
    )
    print(
        f"table {len(table)}, complement {_WORDS - len(table)}, "
        f"union on table {len(union & table)}, union off table {len(union - table)}"
    )


if __name__ == "__main__":
    main()
