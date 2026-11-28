"""Pack 17 inputs into the full Malbolge store.

Each 15-bit prefix owns a three-answer word. Its fourth answer occupies
one of three slots in a shared spill word. A marker per address column
selects a permutation of the eight legal source instructions. A finite
cover of SAT-calibrated lookups handles the words used during navigation.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from functools import cache
from itertools import product
from pathlib import Path
from typing import NamedTuple

from esolangs.languages.malbolge.generator.digits import _readouts
from esolangs.languages.malbolge.generator.isa import _ACTIVE, _WORDS, _char_for
from esolangs.languages.malbolge.interpreter import _XLAT2, _Machine, _op
from esolangs.runtime.io import ScriptedIO

_DATA = Path(__file__).resolve().parent
_ROWS = (
    (45112, 45113, 45114),
    (127032, 127033, 127034),
    (63584, 63585, 63586, 82016, 82017, 82018),
    (7180, 7181, 7182),
    (105484, 105485, 105486),
    (89100, 89101, 89102),
    (7183, 39951),
)
_SPILL_SLOTS = {7183: 2, 39951: 1}
# All other occupied words can take any of the eight source instructions.
_SOURCE_OPS = {
    29524: "*/<ijopv",
    29525: "o",
    29526: "o",
    29527: "o",
    29528: "i",
    39391: "<vo",
    39394: _ACTIVE,
    41391: "oj",
    54677: "o",
    54678: "*",
    59035: "*/<ijov",
    # j here and raw 67 at 29530 halt empty on input 89100.
    59036: "*<iopv",
    59037: "*/<jopv",
}
_TAPS = (139, 127, 130)
_PRINTERS = (4513, 4663, 4585)
_SHORT = ("ojojjjo*oopp", "ojojjooojo*oopp")
_LONG = ("ojoooooooojojojjooojo*oopp", "ojoooooooojojojjjo*oopp")


class _Decoder(NamedTuple):
    source: bytes
    hubs: tuple[int, ...]
    locations: tuple[tuple[int, int, int], ...]
    occupied: bytes
    columns: dict[int, list[int]]


class _Column(NamedTuple):
    marker: int
    labels: dict[int, str]
    fixed: dict[int, str]


type _SelectorGroup = dict[int, list[tuple[int, int]]]

type _Layout = tuple[bytes, tuple[int, ...]]


def _at(machine: _Machine, target: int) -> None:
    for _ in range(15000):
        if machine.ip == target:
            return
        if machine.halted:
            break
        machine.step()
    raise AssertionError(f"decoder missed instruction {target}")


def _high_cell(word: int) -> int:
    """Return the high lookup operand for the payload word's band."""
    return (word - 1) // 243 * 243 + 79


@cache
def _decoder() -> _Decoder:
    """Assemble the decoder and follow its three spill routes from reset."""
    source = bytearray(_char_for("o", k) for k in range(_WORDS))
    for line in (_DATA / "packed-decoder.txt").read_text(encoding="ascii").splitlines():
        address, ops = line.split()
        lo = int(address)
        source[lo : lo + len(ops)] = [_char_for(op, lo + i) for i, op in enumerate(ops)]
    readouts = _readouts(16)
    # Primary and spill words occupy the same high bands.
    for k in {_high_cell(w + 1) for w in readouts}:
        source[k] = _char_for("p", k)
    machine = _Machine(source.decode("ascii"), ScriptedIO("0" * 17))
    _at(machine, 5024)
    # The marker selects which base-nine digit the spill routine replaces.
    directions = {}
    for marker in {source[57592 + w % 729] for w in readouts}:
        d = marker + 1
        for pc in range(5025, 5046):
            if _op(machine.memory[pc], pc) == "j":
                d = machine.memory[d]
            d = (d + 1) % _WORDS
        directions[marker] = {24908: 0, 11786: 1, 31388: 2}[machine.memory[d] + 1]
    _at(machine, 4513)
    hubs = tuple(machine.memory[v + 4] + 1 for v in range(127))
    used = bytearray(_WORDS)
    locations = []
    for w in readouts:
        axis = directions[source[57592 + w % 729]]
        place = 9**axis
        digit = (w // place) % 9
        spill = w + 1 + ((7, 8, 3)[axis] - digit) * place
        slot = (digit // (3, 1, 1)[axis] + 1) % 3
        locations.append((w + 1, spill, slot))
        used[w + 1] = 7
        used[spill] |= 1 << slot
    columns: defaultdict[int, list[int]] = defaultdict(list)
    for word, occupied in enumerate(used):
        if occupied:
            columns[(word - 1) % 243].append(word)
    return _Decoder(bytes(source), hubs, tuple(locations), bytes(used), dict(columns))


@cache
def _layouts() -> tuple[_Layout, ...]:
    """Read the calibrated lookup and printer order pairs in selection order."""
    lookups = (_DATA / "packed-lookups.txt").read_bytes().splitlines()
    layouts = []
    for line in (
        (_DATA / "packed-settings.txt").read_text(encoding="ascii").splitlines()
    ):
        index, order = line.split()
        layouts.append((lookups[int(index)], tuple(map(int, order))))
    return tuple(layouts)


def _polarity_flips() -> tuple[tuple[int, ...], ...]:
    """Project each printer polarity onto the selector row order."""
    return tuple(
        tuple(
            sum(
                ((polarity >> _SPILL_SLOTS.get(row, row % 4)) & 1) << j
                for j, row in enumerate(group)
            )
            for polarity in range(8)
        )
        for group in _ROWS
    )


_POLARITY_FLIPS = _polarity_flips()


# Try the widest group first. A rejected layout needs no other masks.
_GROUP_ORDER = tuple(sorted(range(len(_ROWS)), key=lambda i: -len(_ROWS[i])))


@cache
def _group_choices(lookup: bytes, perm: tuple[int, ...], group: int) -> tuple[int, ...]:
    """Index each local pattern by its compatible printer polarities."""
    mask = _group_mask(lookup, perm, group)
    flips = _POLARITY_FLIPS[group]
    return tuple(
        sum(1 << i for i, flip in enumerate(flips) if mask >> (pattern ^ flip) & 1)
        for pattern in range(1 << len(_ROWS[group]))
    )


def _selection(table: str) -> tuple[bytes, tuple[int, ...], int]:
    """Use the first compatible layout and printer polarity."""
    patterns = tuple(
        sum(int(table[row]) << j for j, row in enumerate(rows)) for rows in _ROWS
    )
    for lookup, perm in _layouts():
        polarities = 255
        for group in _GROUP_ORDER:
            polarities &= _group_choices(lookup, perm, group)[patterns[group]]
            if not polarities:
                break
        else:
            return lookup, perm, (polarities & -polarities).bit_length() - 1
    raise AssertionError("selector coverage is incomplete")


def _pattern(
    source: bytearray,
    hubs: tuple[int, ...],
    perm: tuple[int, ...],
    k: int,
    raw: int,
    marker: int,
    used: int,
) -> int:
    """Read the requested output slots through their three physical lookup taps."""
    high = _char_for("p", _high_cell(k))
    key = 5113 + 3 * _char_for("p", 19745 + high - raw) - marker
    bits = 0
    for slot, virt in enumerate(perm):
        if used >> slot & 1:
            hub = hubs[source[key + _TAPS[virt]]]
            if hub == 41551:
                bits |= 1 << slot
            elif hub != 45925 and (not virt or hub != 54673):
                return -1
    return bits


def _marker_labels(
    source: bytearray, hubs: tuple[int, ...], perm: tuple[int, ...], col: int
) -> Iterator[tuple[int, dict[int, str]]]:
    """Yield column markers with all eight ordinary labels."""
    # Advancing 243 words shifts both raw and high by -243 modulo 94.
    # Their difference, and thus the ordinary label, depends only on the column.
    rep = col + 1
    for marker_op in _ACTIVE:
        marker = _char_for(marker_op, 51031 + 3 * col)
        if marker < 83:
            continue
        labels = {}
        for op in _ACTIVE:
            label = _pattern(source, hubs, perm, rep, _char_for(op, rep), marker, 7)
            if label < 0 or label in labels:
                break
            labels[label] = op
        else:
            yield marker, labels


def _operand_patterns(
    source: bytearray,
    hubs: tuple[int, ...],
    perm: tuple[int, ...],
    word: int,
    marker: int,
    used: int,
) -> Iterator[tuple[str, int]]:
    """Yield the patterns of legal operands at a navigation word."""
    for op in _SOURCE_OPS[word]:
        raw = _char_for(op, word)
        if 29524 <= word <= 29527:
            raw = ord(_XLAT2[raw - 33])
        bits = _pattern(source, hubs, perm, word, raw, marker, used)
        if bits >= 0:
            yield op, bits


def _column_options(
    source: bytearray,
    hubs: tuple[int, ...],
    perm: tuple[int, ...],
    col: int,
    required: tuple[int, ...],
    answers: bytearray,
    used: bytes,
) -> Iterator[_Column]:
    """Yield bijective ordinary labels and legal operands for the navigation words."""
    for marker, labels in _marker_labels(source, hubs, perm, col):
        options = [
            [
                op
                for op, bits in _operand_patterns(
                    source, hubs, perm, k, marker, used[k]
                )
                if bits == answers[k]
            ]
            for k in required
        ]
        for ops in product(*options):
            yield _Column(marker, labels, dict(zip(required, ops, strict=True)))


def _coupled_operands(left: str, right: str) -> bool:
    """Allow operands whose two-word pointer walk rejoins."""
    return left == "<" or right not in "jv"


@cache
def _selector_groups() -> tuple[_SelectorGroup, ...]:
    """Map each selector pattern bit to its operand word and slot."""
    decoder = _decoder()
    groups = []
    for rows in _ROWS:
        words: defaultdict[int, list[tuple[int, int]]] = defaultdict(list)
        for bit, row in enumerate(rows):
            primary, spill, slot = decoder.locations[row // 4]
            word, word_bit = (spill, slot) if row % 4 == 3 else (primary, row % 4)
            words[word].append((word_bit, bit))
        groups.append(dict(words))
    return tuple(groups)


def _group_mask(lookup: bytes, perm: tuple[int, ...], group: int) -> int:
    """Read the compatibility mask from the lookup and legal operands."""
    decoder = _decoder()
    source = bytearray(decoder.source)
    source[5213:5548] = lookup
    # Within a selector group, each operand has its own marker.
    domains = {
        word: {
            (op, sum((bits >> slot & 1) << bit for slot, bit in slots))
            for marker, _ in _marker_labels(
                source, decoder.hubs, perm, (word - 1) % 243
            )
            for op, bits in _operand_patterns(
                source, decoder.hubs, perm, word, marker, decoder.occupied[word]
            )
        }
        for word, slots in _selector_groups()[group].items()
    }
    if len(domains) == 1:
        patterns = {bits for _, bits in next(iter(domains.values()))}
    else:
        patterns = {
            a | b
            for left, a in domains[39391]
            for right, b in domains[39394]
            if _coupled_operands(left, right)
        }
    return sum(1 << bits for bits in patterns)


def _install_layout(
    source: bytearray, lookup: bytes, perm: tuple[int, ...], polarity: int
) -> None:
    """Place the calibrated lookup and the three straight-line printers."""
    source[5213:5548] = lookup
    for slot, virt in enumerate(perm):
        old = _PRINTERS[slot]
        pc = old + _TAPS[virt] - _TAPS[slot]
        for k in range(old, pc):
            source[k] = _char_for("o", k)
        printer = (_SHORT if virt == 0 else _LONG)[polarity >> slot & 1]
        for i, op in enumerate("joooj" + printer + "<v", pc):
            source[i] = _char_for(op, i)


def _packed_program(table: str) -> str:
    """Emit three primary answers and one spill answer per 15-bit prefix."""
    lookup, perm, polarity = _selection(table)
    base, hubs, blocks, used, columns = _decoder()
    source = bytearray(base)
    _install_layout(source, lookup, perm, polarity)
    answers = bytearray(_WORDS)
    for i, (primary, spill, slot) in enumerate(blocks):
        a, b, c, d = map(int, table[4 * i : 4 * i + 4])
        answers[primary] = (a + 2 * b + 4 * c) ^ polarity
        answers[spill] |= (d ^ (polarity >> slot & 1)) << slot
    chosen: dict[int, _Column] = {}
    coupled: dict[int, list[_Column]] = {}
    for col, words in columns.items():
        req = tuple(k for k in words if k in _SOURCE_OPS)
        opts = _column_options(source, hubs, perm, col, req, answers, used)
        if col in (24, 27):
            coupled[col] = list(opts)
        else:
            chosen[col] = next(opts)
    # The two-word pointer walk rejoins with either word varied when '<' is
    # first. The other two first words exclude j and v at the second operand.
    chosen[24], chosen[27] = next(
        (left, right)
        for left in coupled[24]
        for right in coupled[27]
        if _coupled_operands(left.fixed[39391], right.fixed[39394])
    )
    for col, words in columns.items():
        marker, labels, fixed = chosen[col]
        source[51031 + 3 * col] = marker
        for k in words:
            op = fixed[k] if k in fixed else labels[answers[k]]
            source[k] = _char_for(op, k)
    return source.decode("ascii")
