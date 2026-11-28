"""Check storage independence and the complete 17-input selector cover."""

from __future__ import annotations

from collections import defaultdict
from itertools import product

from esolangs.languages.malbolge.generator import packed
from esolangs.languages.malbolge.generator.isa import _ACTIVE, _WORDS, _char_for
from esolangs.languages.malbolge.interpreter import _XLAT2

# Full reconstruction took 2.1 s on the reference machine.
BAND = "by-hand"
COST = 3.5


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
    markers = {51031 + 3 * col for col in decoder.columns}
    high_words = {((word - 1) // 243) * 243 + 79 for word in words}
    spill_routes = {57592 + (primary - 1) % 729 for primary, _, _ in decoder.locations}
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
    perm: tuple[int, ...],
) -> dict[int, list[_Choice]]:
    """Collect all legal word/marker combinations for each shared column."""
    source = bytearray(decoder.source)
    source[5213:5548] = lookup
    domains: dict[int, list[_Choice]] = {}
    for column, occupied in decoder.columns.items():
        words = [word for word in occupied if word in rows]
        choices = []
        for op in _ACTIVE:
            marker = _char_for(op, 51031 + 3 * column)
            if marker < 83:
                continue
            rep = column + 1
            labels = {
                packed._pattern(
                    source, decoder.hubs, perm, rep, _char_for(o, rep), marker, 7
                )
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
                        perm,
                        word,
                        raw,
                        marker,
                        decoder.occupied[word],
                    )
                    if bits >= 0:
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


def main() -> int:
    """Recompute the masks from executable bytes and intersect every requested group."""
    layout = packed._decoder()
    rows = _rows_by_word(layout)
    choices = [[0] * (1 << len(group)) for group in packed._ROWS]
    for i, (lookup, perm) in enumerate(packed._layouts()):
        masks = _masks(_domains(layout, rows, lookup, perm))
        for group, (combined, mask) in enumerate(zip(choices, masks, strict=True)):
            assert packed._group_mask(lookup, perm, group) == mask
            for pattern, polarities in enumerate(
                packed._group_choices(lookup, perm, group)
            ):
                combined[pattern] |= polarities << (8 * i)
    assert packed._selector_masks() == tuple(map(tuple, choices))

    # The frontier keeps distinct intersections. An empty intersection witnesses
    # an uncovered assignment even when two requested prefixes share a mask.
    frontier = {-1}
    for patterns in sorted(choices, key=len, reverse=True):
        frontier = {mask & local for mask in frontier for local in patterns}
        assert 0 not in frontier
    width = sum(map(len, packed._ROWS))
    print(
        f"Malbolge: {1 << 17:,} distinct slots, "
        f"all {1 << width:,} selector assignments covered"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
