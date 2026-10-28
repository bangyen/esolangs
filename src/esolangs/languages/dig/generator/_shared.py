"""Shared Dig lookup bodies selected by an arithmetic prefix index."""

from typing import NamedTuple

from esolangs.generation.helpers import essential_inputs, read_at
from esolangs.languages.dig.generator._layout import (
    _dig_alt_clear,
    _Point,
    _remap_reads,
)
from esolangs.languages.dig.generator._leaf import (
    _DIG_OPAQUE,
    _DIG_TURNS_CW,
    _dig_adder,
    _dig_adder_fits,
    _dig_flat_leaf,
    _hold_column,
    _Reads,
    _render,
)


class _PrefixDecoder(NamedTuple):
    """A prefix decoder stamp plus the geometry the shared body needs.

    ``end`` is the exit column, ``last`` the stamp-local point the decoder
    is left from, and ``offset``/``row_offset``/``top`` place and bound it on
    the grid.
    """

    chars: dict[tuple[int, int], str]
    turns: dict[tuple[int, int], int]
    reads: _Reads
    end: int
    last: tuple[int, int]
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
        offset=1,
        row_offset=row_offset,
        top=box.max_y + row_offset + 3,
    )


def _bit_prefix_decoder() -> _PrefixDecoder:
    """Read one prefix bit and leave it as the class label.

    Two classes in first-appearance order are labelled 0 and 1, which is
    the bit itself, so no digit lookup follows the read.
    """
    return _PrefixDecoder(
        {(0, 0): "$", (-1, 0): "1", (0, 1): "~"},
        {(0, 2): 1},
        [((0, 0), (-1, 0), frozenset())],
        end=2,
        last=(0, 2),
        offset=1,
        row_offset=1,
        top=4,
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
        reads = _remap_reads(reads, shift)
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
    return _PrefixDecoder(
        chars,
        turns,
        reads,
        end=end,
        last=(len(prefix) + 4, end),
        offset=1,
        row_offset=1,
        top=len(prefix) + 8,
    )


#: Column the shared body's entry sits on, east of the decoder's descent.
_BODY_ENTRY_COL = 11


def _leaf_weights(live: list[bool]) -> list[int]:
    """Place values over a leaf adder's inputs, an ignored one weighing 0."""
    count = sum(live)
    weights, seen = [], 0
    for kept in live:
        seen += kept
        weights.append(1 << (count - seen) if kept else 0)
    return weights


def _indexed_classes(table: str, keep: list[int]) -> tuple[list[str], str] | None:
    """Return the distinct leaf classes and each block's class label.

    Each 64-entry block is read at its ``keep`` inputs.  None unless the
    table holds two to ten classes, the range the prefix decoder can label
    with one digit each.
    """
    blocks = [read_at(table[i : i + 64], keep, 6) for i in range(0, len(table), 64)]
    unique = list(dict.fromkeys(blocks))
    if not 2 <= len(unique) <= 10:
        return None
    indices = {block: str(i) for i, block in enumerate(unique)}
    return unique, "".join(indices[block] for block in blocks)


def _dig_indexed_shared(table: str, n: int) -> str | None:
    """Decode one to six prefix bits into shared six-input leaf classes.

    Prefix literals become inert after the selected class is read. Its
    class number adds eight rows to the final six-input lookup per class.
    Ignored inputs just before and after the leaf ride its adders as zero
    weights, as do ignored ones among its six.
    """
    if n < 7:
        return None
    essential = set(essential_inputs(table, n))
    trail = n - 1 - max(essential, default=n - 1)
    before = 0
    # Ignored inputs just before the leaf: the zeros the high adder reads.
    while n - trail - 7 - before >= 1 and n - trail - 7 - before not in essential:
        before += 1
    for lead, tail in ((before, trail), (0, 0)):
        built = _indexed_build(table, n, essential, lead, tail)
        if built is not None:
            return built
    return None


def _indexed_build(
    table: str, n: int, essential: set[int], lead: int, trail: int
) -> str | None:
    """Build the indexed program, or None when it does not fit.

    ``lead`` ignored inputs sit before the leaf's six, ``trail`` after.
    """
    end = n - trail
    start = end - 6
    drop = range(start - lead, start)
    table = read_at(table, [i for i in range(end) if i not in drop], n)
    bits = start - lead
    if bits not in (1, 2, 3, 4, 5, 6):
        return None
    live = [start + i in essential for i in range(6)]
    # An adder stores every live input but its last, so each needs a live one
    # among its first two; one without keeps its three inputs.
    if not (live[0] or live[1]):
        live[:3] = [True] * 3
    if not (live[3] or live[4]):
        live[3:] = [True] * 3
    high = [0] * lead + _leaf_weights(live[:3])
    low = _leaf_weights(live[3:]) + [0] * trail
    if not (_dig_adder_fits(high, 2) and _dig_adder_fits(low, 0)):
        return None
    classes = _indexed_classes(table, [i for i in range(6) if live[i]])
    if classes is None:
        return None
    unique, prefix = classes
    if bits == 1:
        decoder = _bit_prefix_decoder()
    elif bits > 4:
        decoder = _flat_prefix_decoder(bits, prefix)
    else:
        decoder = _adder_prefix_decoder(bits, prefix)
    return _assemble_indexed(decoder, unique, high, low)


def _assemble_indexed(
    decoder: _PrefixDecoder, unique: list[str], high: list[int], low: list[int]
) -> str:
    """Place the decoder above the shared body, clear and render the grid."""
    chars, turns, reads, _exit, _ = _dig_flat_leaf(
        "".join(unique),
        high,
        low,
        classes=len(unique),
    )
    # The descent runs down the first column from 11 on that the painter's two
    # rows leave clear of turns and opaque commands; a leading ignored input
    # puts the painter's last turn on 11.
    blocked = {c for (r, c) in turns if r in (0, 1)}
    blocked |= {c for (r, c), ch in chars.items() if r in (0, 1) and ch in _DIG_OPAQUE}
    capture = max(c for (r, c), ch in chars.items() if r == 2 and ch == "$")
    merge = max(_BODY_ENTRY_COL, capture + 2)
    while merge in blocked:
        merge += 1

    def place(point: tuple[int, int]) -> tuple[int, int]:
        return point[0] + decoder.row_offset, point[1] + decoder.offset

    cells = {place(p): c for p, c in decoder.chars.items()}
    cells.update({place(p): _DIG_TURNS_CW[h] for p, h in decoder.turns.items()})
    checks = _remap_reads(decoder.reads, place)
    cells[0, 0], cells[decoder.row_offset, 0] = "'", ">"
    cells[decoder.top - 2, decoder.end + decoder.offset] = ">"
    cells[decoder.top - 2, merge] = "'"
    # The mole walks the capture row west to its ``$``.

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
        ((decoder.top + 2, merge), 3, merge - capture),
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
