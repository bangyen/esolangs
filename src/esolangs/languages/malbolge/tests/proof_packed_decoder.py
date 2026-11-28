"""Check packed storage independence and certify selector coverage."""

from __future__ import annotations

from collections import defaultdict
from itertools import product

from esolangs.languages.malbolge.generator import packed
from esolangs.languages.malbolge.generator.isa import _ACTIVE, _WORDS, _char_for
from esolangs.languages.malbolge.generator.lookup_diagram import ALL_PHASES, Diagram
from esolangs.languages.malbolge.generator.lookup_projection import (
    _WITNESS_LIMIT,
    project,
    select_bounded,
)
from esolangs.languages.malbolge.generator.lookup_request import (
    prepare,
    selector_axes,
    unpack_request,
)
from esolangs.languages.malbolge.generator.packed_layout import (
    _BANK,
    _LOOKUP,
    _SPILL_MARKER_BASE,
    _column_marker,
    _high_cell,
)
from esolangs.languages.malbolge.interpreter import _XLAT2

BAND = "by-hand"
COST = 8.0


def _rows_by_word(decoder: packed._Decoder) -> dict[int, list[tuple[int, int]]]:
    """Require all physical bit positions to be distinct, including partial spills."""
    occupied = bytearray(_WORDS)
    rows: defaultdict[int, list[tuple[int, int]]] = defaultdict(list)
    for prefix, (primary, spill, slot) in enumerate(decoder.locations):
        for suffix, (word, bit) in enumerate(
            ((primary, 0), (primary, 1), (primary, 2), (spill, slot))
        ):
            assert not occupied[word] & (1 << bit)
            occupied[word] |= 1 << bit
            if word in packed._SOURCE_OPS:
                rows[word].append((4 * prefix + suffix, bit))
    words = {word for word, mask in enumerate(occupied) if mask}
    markers = {_column_marker(col) for col in decoder.columns}
    high_words = {_high_cell(word) for word in words}
    spill_routes = {
        _SPILL_MARKER_BASE + (primary - 1) % _BANK
        for primary, _, _ in decoder.locations
    }
    assert words.isdisjoint(markers | high_words | spill_routes)
    assert markers.isdisjoint(high_words | spill_routes)
    assert all(decoder.source[k] == _char_for("p", k) for k in high_words)
    assert occupied == decoder.occupied
    assert sum(v.bit_count() for v in occupied) == 1 << 17
    return dict(rows)


type _Answers = dict[int, int]
type _Choice = tuple[dict[int, str], _Answers]


def _domains(
    decoder: packed._Decoder,
    rows: dict[int, list[tuple[int, int]]],
    lookup: bytes,
) -> dict[int, list[_Choice]]:
    """Collect all legal word/marker combinations for each shared column."""
    source = bytearray(decoder.source)
    source[_LOOKUP.start : _LOOKUP.stop] = lookup
    domains: dict[int, list[_Choice]] = {}
    for column, occupied in decoder.columns.items():
        words = [word for word in occupied if word in rows]
        choices = []
        for op in _ACTIVE:
            marker = _char_for(op, _column_marker(column))
            if marker < 83:
                continue
            rep = column + 1
            labels = {
                packed._pattern(source, decoder.hubs, rep, _char_for(o, rep), marker, 7)
                for o in _ACTIVE
            }
            if labels != set(range(8)):
                continue
            if not words:
                break
            values = []
            for word in words:
                valid = []
                for opcode in packed._SOURCE_OPS[word]:
                    raw = _char_for(opcode, word)
                    if 29524 <= word <= 29527:
                        raw = ord(_XLAT2[raw - 33])
                    bits = packed._pattern(
                        source,
                        decoder.hubs,
                        word,
                        raw,
                        marker,
                        decoder.occupied[word],
                    )
                    if bits is not None:
                        valid.append((opcode, bits))
                values.append(valid)
            for assignment in product(*values):
                opcodes = {w: o for w, (o, _) in zip(words, assignment, strict=True)}
                answers = {
                    r: (bits >> b) & 1
                    for w, (_, bits) in zip(words, assignment, strict=True)
                    for r, b in rows[w]
                }
                choices.append((opcodes, answers))
        else:
            assert choices, column
        if words:
            domains[column] = choices

    left, right = domains.pop(24), domains.pop(27)
    domains[24] = [
        (a | b, x | y)
        for a, x in left
        for b, y in right
        if a[39391] == "<" or b[39394] not in "jv"
    ]
    return domains


def _masks(domains: dict[int, list[_Choice]]) -> tuple[int, ...]:
    masks = {}
    for options in domains.values():
        rows = sorted(options[0][1])
        group = next((g for g in packed._ROWS if set(g) <= set(rows)), ())
        patterns = {
            sum(answers[r] << i for i, r in enumerate(group)) for _, answers in options
        }
        # Every assignment outside the selector group must be independently available.
        full = {tuple(a[r] for r in rows) for _, a in options}
        assert len(full) == len(patterns) << (len(rows) - len(group))
        if group:
            masks[group] = sum(1 << v for v in patterns)
    return tuple(masks[g] for g in packed._ROWS)


def _certify(physical: int, width: int) -> int:
    """Return its exact output mask and check the uniform witness allocation bound."""
    bound = ALL_PHASES + 1

    def account(arena: Diagram, root: int, _variable: int, colors: int) -> None:
        nonlocal bound
        bound += arena.color_nodes(root, colors)

    arena, root = project(prepare(physical), physical, account)
    assert bound <= _WITNESS_LIMIT, (physical, bound)
    return arena.truth_mask(root, width)


def _flip_axes(mask: int, changed: int, full: int) -> int:
    """XOR selected output axes by swapping the corresponding bitset halves."""
    while changed:
        bit = changed & -changed
        stride = 1 << (bit.bit_length() - 1)
        low = full // ((1 << stride) + 1)
        mask = ((mask & low) << stride) | ((mask & (full ^ low)) >> stride)
        changed ^= bit
    return mask


def check_cover() -> None:
    """Prove selector totality and bound the allocation for every witness."""
    width, pin, axes = selector_axes()
    full = (1 << (1 << width)) - 1
    physical = tuple(_certify(answer, width) for answer in range(1 << len(pin)))
    flips = tuple(
        sum(
            1 << axis
            for word in axes.values()
            for slot, axis in word.items()
            if phase >> slot & 1
        )
        for phase in range(7)
    )
    for logical in range(1 << len(pin)):
        covered = 0
        for phase, flip in enumerate(flips):
            if covered != full:
                covered |= _flip_axes(physical[logical ^ phase], flip, full)
        assert covered == full, logical

    print(f"Malbolge: all {1 << (width + len(pin)):,} selector assignments covered")


def main() -> int:
    """Verify slot independence and one reconstructed lookup in the proof band."""
    decoder = packed._decoder()
    rows = _rows_by_word(decoder)
    groups = packed._selector_groups()
    # Evaluate the emitted layout independently of the projected factors.
    lookup, phase = select_bounded(unpack_request((0,) * len(groups)))
    masks = _masks(_domains(decoder, rows, lookup))
    for group, mask in zip(groups, masks, strict=True):
        bits = sum(
            (phase >> slot & 1) << row
            for entries in group.values()
            for slot, row in entries
        )
        assert mask >> bits & 1
    print(f"Malbolge: {1 << 17:,} distinct slots and a valid reconstructed lookup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
