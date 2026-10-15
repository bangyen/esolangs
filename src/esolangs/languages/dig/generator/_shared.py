"""Shared Dig lookup bodies selected by an arithmetic prefix index."""

from typing import NamedTuple

from esolangs.languages.dig.generator._layout import (
    _dig_alt_clear,
    _Point,
    _remap_reads,
    _walk_bound,
)
from esolangs.languages.dig.generator._leaf import (
    _DIG_TURNS_CW,
    _dig_adder,
    _dig_flat_leaf,
    _dig_flat_walk,
    _hold_column,
    _Reads,
    _render,
)


class _PrefixDecoder(NamedTuple):
    """A prefix decoder stamp plus the geometry the shared body needs.

    ``end`` is the exit column, ``last`` the stamp-local point the decoder
    is left from, ``prefix_cost`` its walk, ``exit_row`` its exit row, and
    ``offset``/``row_offset``/``top`` place and bound it on the grid.
    """

    chars: dict[tuple[int, int], str]
    turns: dict[tuple[int, int], int]
    reads: _Reads
    end: int
    last: tuple[int, int]
    prefix_cost: int
    exit_row: int
    offset: int
    row_offset: int
    top: int


def _flat_prefix_decoder(bits: int, prefix: str) -> _PrefixDecoder:
    """Decode the prefix with a flat stamp, blanking its output for reuse.

    The output ``:`` and the halt ``@`` become ordinary cells; the body's
    corridor later enters through the halt's position.
    """
    high_bits = bits - bits // 2
    high = [1 << i for i in reversed(range(high_bits))]
    low = [1 << i for i in reversed(range(bits // 2))]
    chars, turns, reads, _exit, box = _dig_flat_leaf(prefix, high, low)
    output = next(p for p, char in chars.items() if char == ":")
    halt = next(p for p, char in chars.items() if char == "@")
    chars[output] = " "
    turns[halt] = 1
    del chars[halt]
    row_offset = 2 - box.min_y
    return _PrefixDecoder(
        chars,
        turns,
        reads,
        end=halt[1],
        last=halt,
        prefix_cost=_dig_flat_walk(high, low),
        exit_row=halt[0],
        offset=1,
        row_offset=row_offset,
        top=box.max_y + row_offset + 3,
    )


def _adder_prefix_decoder(bits: int, prefix: str) -> _PrefixDecoder:
    """Decode the prefix with an adder, chaining the prefix digits east."""
    chars, turns, reads, exit_at, _ = _dig_adder(
        [1 << i for i in reversed(range(bits))], 1
    )
    if bits == 4:
        # The third product begins a second window; both counts fit one digit.
        cut = 8

        def shift(point: tuple[int, int]) -> tuple[int, int]:
            return point[0], point[1] + int(point[1] >= cut)

        chars = {shift(p): c for p, c in chars.items()}
        turns = {shift(p): h for p, h in turns.items()}
        reads = [
            (shift(at), shift(want), frozenset(shift(p) for p in pending))
            for at, want, pending in reads
        ]
        chars[-1, 0], chars[0, cut], chars[-1, cut] = "7", "$", "4"
        hold = _hold_column(chars)
        chars[0, hold] = str(hold - exit_at[1] - 1)
        reads.append(((0, cut), (-1, cut), frozenset()))
    end = exit_at[1]
    turns[1, end] = 1
    chars[2, end], chars[2, end - 1] = "$", "1"
    chars[3, end], chars[4, end] = ";", "$"
    reads.extend(
        (
            ((2, end), (2, end - 1), frozenset({(3, end)})),
            ((4, end), (3, end), frozenset()),
        )
    )
    chars.update({(row, end): char for row, char in enumerate(prefix, 5)})
    hold = _hold_column(chars)
    return _PrefixDecoder(
        chars,
        turns,
        reads,
        end=end,
        last=(len(prefix) + 4, end),
        prefix_cost=2 * hold + 4 - end,
        exit_row=1,
        offset=1,
        row_offset=1,
        top=len(prefix) + 8,
    )


def _dig_indexed_shared(table: str, n: int) -> str | None:
    """Decode two to six prefix bits into shared six-input leaf classes.

    Prefix literals become inert after the selected class is read. Its
    class number adds eight rows to the final six-input lookup per class.
    Entry and stamp legs are charged against the unchanged command ledger.
    """
    bits = n - 6
    if bits not in (2, 3, 4, 5, 6):
        return None
    blocks = [table[i : i + 64] for i in range(0, len(table), 64)]
    unique = list(dict.fromkeys(blocks))
    if not 2 <= len(unique) <= 10:
        return None
    indices = {block: str(i) for i, block in enumerate(unique)}
    prefix = "".join(indices[block] for block in blocks)
    decoder = (
        _flat_prefix_decoder(bits, prefix)
        if bits > 4
        else _adder_prefix_decoder(bits, prefix)
    )
    merge = 11
    # Entry, decoder, descent, east/down/west connection, shared body.
    rows = 8
    body_cost = (
        _dig_flat_walk([4, 2, 1], [4, 2, 1])
        - ((rows + 14) // 2 - 1)
        + 9
        + 3 * rows * (len(unique) - 1)
    )
    cost = (
        decoder.row_offset
        + decoder.offset
        + decoder.prefix_cost
        + decoder.top
        - 2
        - (decoder.exit_row + decoder.row_offset)
        + merge
        - (decoder.end + decoder.offset)
        + 4
        + merge
        - 9
        + body_cost
    )
    if cost > _walk_bound(n):
        return None

    def place(point: tuple[int, int]) -> tuple[int, int]:
        return point[0] + decoder.row_offset, point[1] + decoder.offset

    cells = {place(p): c for p, c in decoder.chars.items()}
    cells.update({place(p): _DIG_TURNS_CW[h] for p, h in decoder.turns.items()})
    checks = _remap_reads(decoder.reads, place)
    cells[0, 0], cells[decoder.row_offset, 0] = "'", ">"
    cells[decoder.top - 2, decoder.end + decoder.offset] = ">"
    cells[decoder.top - 2, merge] = "'"
    chars, turns, reads, _exit, _ = _dig_flat_leaf(
        "".join(unique), [4, 2, 1], [4, 2, 1], classes=len(unique)
    )

    def below(point: tuple[int, int]) -> tuple[int, int]:
        return point[0] + decoder.top, point[1]

    cells.update({below(p): c for p, c in chars.items()})
    cells.update({below(p): _DIG_TURNS_CW[h] for p, h in turns.items()})
    checks.extend(_remap_reads(reads, below))
    cells[decoder.top + 2, merge] = "<"
    last = place(decoder.last)
    corridors = [
        ((0, 0), 2, decoder.row_offset),
        ((decoder.row_offset, 0), 1, decoder.offset),
        (last, 2, decoder.top - 2 - last[0]),
        (
            (decoder.top - 2, decoder.end + decoder.offset),
            1,
            merge - (decoder.end + decoder.offset),
        ),
        ((decoder.top - 2, merge), 2, 4),
        ((decoder.top + 2, merge), 3, merge - 8),
    ]
    _dig_alt_clear(
        {_Point(*p): c for p, c in cells.items()},
        [
            (_Point(*at), _Point(*want), frozenset(_Point(*p) for p in pending))
            for at, want, pending in checks
        ],
        [(_Point(*p), h, d) for p, h, d in corridors],
    )
    return _render(cells, dense=True)
