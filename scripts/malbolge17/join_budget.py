"""Measure the current address and decoder maps against the 17-input table."""

from __future__ import annotations

import argparse
import itertools
from collections import defaultdict

from address17 import ALL2, group_word
from address_gadget import build as build_address
from decoder_group import _build as build_decoder
from decoder_group import _setup as setup_decoder

from esolangs.interpreters.other.malbolge import (
    _advance,
    _crazy,
    _initial_memory,
    _op,
)
from esolangs.tools.malbolge.core import _WORDS


def _executed(source: str, bits: tuple[int, ...]) -> set[int]:
    """Return instruction addresses visited by one emitted address path."""
    memory = list(_initial_memory(source))
    state = (0, 0, 0, False)
    inputs = iter(48 + bit for bit in bits)
    seen: set[int] = set()
    for _ in range(100_000):
        seen.add(state[1])
        char = next(inputs) if _op(memory[state[1]], state[1]) == "/" else None
        state, writes, _ = _advance(state, memory, char)
        for address, value in writes:
            memory[address] = value
        if state[3]:
            return seen
    raise AssertionError("address fold did not halt")


def main(
    *,
    live: bool = False,
    components: bool = False,
    guard_scratch: bool = False,
    prepare_returns: bool = False,
    result_first: bool = False,
    slot_pointers: bool = False,
) -> None:
    """Report exact occupied-cell counts for the current separate emitters."""
    address_cells: set[int] = set()
    address_parts: list[tuple[str, set[int]]] = []
    source, groups, _, count = build_address(
        z=None,
        dispatch_ab=True,
        parity=True,
        high_pointer=True,
        high_parity=True,
        occupied=address_cells,
        part_cells=address_parts,
        guard_scratch=guard_scratch,
        prepare_returns=prepare_returns,
        result_first=result_first,
        slot_pointers=slot_pointers,
    )
    assert groups[-1] == (145, 139, 144)
    address_cells.update(range(10, 18))  # startup precedes the emitted parts
    assert len(address_cells) == count
    decoder = build_decoder(
        0,
        setup_decoder(frozenset({142, 145, 139, 144}), external_pointer=True),
        external_pointer=True,
        external_parity=True,
    )
    assert not {142, 145, 139, 144} & decoder.code.keys()
    assert not {142, 145, 139, 144} & decoder.data.keys()
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
    if components:
        grouped: dict[str, set[int]] = defaultdict(set)
        for name, cells in address_parts:
            grouped[name].update(cells)
        for name, cells in sorted(
            grouped.items(), key=lambda part: -len(part[1] & table)
        ):
            print(
                f"{name}: {len(cells)} cells, {len(cells & table)} on table, "
                f"{len(cells & decoder_cells)} on decoder, "
                f"{len(cells & conflicts)} conflicting"
            )
    if live:
        first = _executed(source, (0,) * 14)
        assert address_cells - first  # positive control for the zero-result audit
        seen = set(first)
        for bits in itertools.product(range(2), repeat=14):
            if any(bits):
                seen.update(_executed(source, bits))
        dead = address_cells - seen
        print(
            f"address liveness: {len(dead)} dead of {len(address_cells)} emitted "
            f"cells; one-path control leaves {len(address_cells - first)} unvisited"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="trace all address paths")
    parser.add_argument("--components", action="store_true", help="list address parts")
    parser.add_argument(
        "--guard-scratch", action="store_true", help="reserve return neighbours"
    )
    parser.add_argument(
        "--prepare-returns", action="store_true", help="emit return setup"
    )
    parser.add_argument(
        "--result-first", action="store_true", help="place result cells before seed"
    )
    parser.add_argument(
        "--slot-pointers", action="store_true", help="emit three low slot pointers"
    )
    args = parser.parse_args()
    main(
        live=args.live,
        components=args.components,
        guard_scratch=(
            args.guard_scratch
            or args.prepare_returns
            or args.result_first
            or args.slot_pointers
        ),
        prepare_returns=args.prepare_returns,
        result_first=args.result_first or args.slot_pointers,
        slot_pointers=args.slot_pointers,
    )
