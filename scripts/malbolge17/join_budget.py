"""Measure the current address and decoder maps against the 17-input table."""

from __future__ import annotations

import argparse
import itertools
from collections import defaultdict

from address17 import table_cells
from address_gadget import build as build_address
from decoder_group import _build as build_decoder
from decoder_group import _setup as setup_decoder
from dispatch3 import emit as build_selector

from esolangs.interpreters.other.malbolge import (
    _advance,
    _initial_memory,
    _op,
)
from esolangs.tools.malbolge.core import _WORDS, _char_for


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


def _address_map(
    *,
    shared_special_fold: bool = False,
    guard_scratch: bool = False,
    prepare_returns: bool = False,
    result_first: bool = False,
    slot_pointers: bool = False,
) -> tuple[
    str, set[int], list[tuple[str, set[int]]], int, tuple[tuple[int, int, int], ...]
]:
    """Return the address source, occupied cells, parts, instruction count and groups.

    ``occupied`` also holds the reserved cell before every emitted ``i``
    destination, so it can exceed the instruction count.
    """
    occupied: set[int] = set()
    parts: list[tuple[str, set[int]]] = []
    source, groups, _, count = build_address(
        z=None,
        dispatch_ab=True,
        parity=True,
        high_pointer=True,
        high_parity=True,
        occupied=occupied,
        part_cells=parts,
        shared_special_fold=shared_special_fold,
        guard_scratch=guard_scratch or shared_special_fold,
        prepare_returns=prepare_returns or shared_special_fold,
        result_first=result_first or shared_special_fold,
        slot_pointers=slot_pointers or shared_special_fold,
    )
    assert groups[-1] == (145, 139, 144)
    occupied.update(range(10, 18))  # startup precedes the emitted parts
    return source, occupied, parts, count, groups


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
    source, address_cells, address_parts, count, _groups = _address_map(
        guard_scratch=guard_scratch,
        prepare_returns=prepare_returns,
        result_first=result_first,
        slot_pointers=slot_pointers,
    )
    emitted = set().union(*(cells for _, cells in address_parts))
    # The returned count covers the eight startup cells and the emitted
    # parts; the occupied set additionally reserves the cell before each
    # emitted instruction, which executing an `i` enciphers, so the two
    # counts differ by the guard cells rather than agreeing.
    assert count == len(emitted) + len(range(10, 18))
    assert address_cells == (
        emitted | {a - 1 for a in emitted if a > 0} | set(range(10, 18))
    )
    decoder = build_decoder(
        0,
        setup_decoder(frozenset({142, 145, 139, 144}), external_pointer=True),
        external_pointer=True,
        external_parity=True,
    )
    assert not {142, 145, 139, 144} & decoder.code.keys()
    assert not {142, 145, 139, 144} & decoder.data.keys()
    decoder_cells = set(decoder.code)
    # The cells the emitted fold actually reads (its pointer+1..+3), not
    # a re-derived approximation: the two conventions differ in 640 cells.
    table = table_cells()
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


def _source_chars(source: str | list[int], cells: set[int]) -> dict[int, int]:
    """Return the required source character at each occupied cell."""
    if isinstance(source, str):
        return {cell: ord(source[cell]) for cell in cells}
    return {cell: source[cell] for cell in cells}


def shared_setup() -> None:
    """Price the address fold, row selector and decoder sharing setup once.

    ``separate`` is the unguarded fold the live trace checks; ``join`` is the
    guarded shared fold the decoder consumers read.  Identical cells are
    counted once in the union.  A cell whose required source character differs
    between components cannot be shared and is reported as a conflict.
    """
    selector = build_selector()
    selector_cells = set(selector.code) | set(selector.data)
    decoder = build_decoder(
        0,
        setup_decoder(frozenset({142, 145, 139, 144}), external_pointer=True),
        external_pointer=True,
        external_parity=True,
    )
    decoder_cells = set(decoder.code) | set(decoder.data)
    complement = _WORDS - 49_152
    variants = {
        "separate": _address_map(),
        "join": _address_map(shared_special_fold=True),
    }
    for name, (
        address_source,
        address_cells,
        _parts,
        count,
        _groups,
    ) in variants.items():
        chars = {
            "address": _source_chars(address_source, address_cells),
            "selector": _source_chars(selector.source, selector_cells),
            "decoder": _source_chars(decoder.source, decoder_cells),
        }
        union = address_cells | selector_cells | decoder_cells
        naive = sum(len(cells) for cells in chars.values())
        collapsed = naive - len(union)
        conflicts = {
            cell
            for cell in union
            if len({cells[cell] for cells in chars.values() if cell in cells}) > 1
        }
        deficit = len(union) - complement
        print(
            f"{name}: address {len(address_cells)} occupied ({count} instructions), "
            f"selector {len(selector_cells)}, decoder {len(decoder_cells)}"
        )
        print(
            f"{name}: naive {naive}, shared union {len(union)}, collapsed {collapsed}, "
            f"conflicts {len(conflicts)}"
        )
        print(
            f"{name}: complement {complement}, deficit {deficit}, "
            f"deficit with conflicting overlaps {deficit + len(conflicts)}"
        )
    sources = []
    for row in range(8):
        group = setup_decoder(
            frozenset({142, 145, 139, 144}),
            external_pointer=True,
            runtime_base=True,
            table_free_hubs=True,
            low_neighbour=True,
        )
        sources.append(
            build_decoder(
                row,
                group,
                external_pointer=True,
                external_parity=True,
                compact=True,
                common_setup=True,
            ).source
        )
    prefix = 0
    for cell in range(_WORDS):
        if len({source[cell] for source in sources}) != 1:
            break
        prefix = cell
    changed = {
        cell
        for cell in range(_WORDS)
        if any(source[cell] != _char_for("o", cell) for source in sources)
    }
    identical = len(
        {cell for cell in changed if len({source[cell] for source in sources}) == 1}
    )
    print(
        f"decoder rows: byte-identical through cell {prefix}; "
        f"{len(changed)} row-written cells, {identical} identical"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="trace all address paths")
    parser.add_argument("--components", action="store_true", help="list address parts")
    parser.add_argument(
        "--shared-setup",
        action="store_true",
        help="price address, selector and decoder with setup shared once",
    )
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
    if args.shared_setup:
        shared_setup()
    else:
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
