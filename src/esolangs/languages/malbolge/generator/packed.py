"""Pack 17 inputs into the full Malbolge store.

Each 15-bit prefix owns a three-answer word. Its fourth answer occupies
one of three slots in a shared spill word. A marker per address column
selects a permutation of the eight legal source instructions. The lookup
and printer polarity are derived from the requested navigation answers.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterator
from functools import cache
from pathlib import Path
from typing import NamedTuple

from esolangs.languages.malbolge.generator.digits import _readouts
from esolangs.languages.malbolge.generator.isa import (
    _ACTIVE,
    _ALL1,
    _WORDS,
    _char_for,
    _progression,
)
from esolangs.languages.malbolge.interpreter import _XLAT2, _Machine
from esolangs.runtime.io import ScriptedIO

from .emitter import _ENCODING_PERIOD
from .spill import _BANK, _spill_locations

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
_LEFT_OPERAND, _RIGHT_OPERAND = 39391, 39394
# All other occupied words can take any of the eight source instructions.
_SOURCE_OPS = {
    29524: "*/<ijopv",
    29525: "o",
    29526: "o",
    29527: "o",
    29528: "i",
    _LEFT_OPERAND: "<vo",
    _RIGHT_OPERAND: _ACTIVE,
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


class _Operand(NamedTuple):
    column: _Column
    op: str


class _Encodings(NamedTuple):
    by_answer: dict[int, _Operand]
    restricted: dict[int, _Operand]


type _SelectorGroup = dict[int, list[tuple[int, int]]]


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


def _write_guard_approaches(source: bytearray) -> None:
    """Install the shared jump that the lookup guards use to enter low memory."""
    # The first jump reads the glyph; six walks reach its pointer operand.
    approach = "j" + "o" * 6 + "jo"
    # The first guard and the printer guard share their next six jumps.
    shared = approach + "j" + "o" * 5 + "jojjojooj"
    for pc, ops in ((5585, shared), (5657, approach), (5697, shared)):
        for address, op in enumerate(ops, pc):
            source[address] = _char_for(op, address)


def _write_guard_returns(source: bytearray) -> None:
    """Route the two dispatch guards through the encrypted all-ones operand."""
    operand = _ALL1 + 1
    landing = ord(_XLAT2[_char_for("o", operand) - 33]) + 1
    return_pointer = 86
    terminal = _progression(return_pointer - 1, landing, 127)[0]
    shared = "j" + "o" * (terminal - landing) + "j"
    # Both low operands contain all-ones when the dispatch guard runs.
    for pc, hub, low, approach in ((5609, 45926, 46, "o"), (5681, 41552, 36, "")):
        walk = low - (source[hub] + 1)
        assert walk >= 0
        ops = approach + "j" + "o" * walk + "j" + shared
        for address, op in enumerate(ops, pc):
            source[address] = _char_for(op, address)


def _short_hub_cell(k: int) -> bool:
    """Return whether the walked pointer cell will name the short hub."""
    residue = k % 20
    return 37 <= k < 125 and (
        residue in (4, 10, 17)
        or (residue == 3 and k < 83)
        or (residue == 11 and k >= 91)
    )


def _one_hub_cell(k: int) -> bool:
    """Return whether the walked pointer cell will name the one hub."""
    residue = k % 20
    return 40 <= k < 128 and (
        residue in (0, 7, 14) or (residue == 13 and k <= 73) or k == 121
    )


def _write_hub_fills(source: bytearray) -> None:
    """Stamp the three hub families into their all-ones pointer cells."""

    def long(k: int) -> bool:
        residue = k % 20
        return (
            (residue in (2, 9, 16) and k != 36)
            or (residue == 15 and k <= 75)
            or (residue == 3 and k >= 103)
        )

    def scan(lo: int, hi: int, belongs: Callable[[int], bool]) -> str:
        return "".join("p" if belongs(k) else "o" for k in range(lo, hi))

    # The short and long families walk through their full ranges.
    # The one family skips gaps via the walked reset operands and the
    # primed all-ones cell at D55, which leads through the encrypted neighbor.
    one_fill = (
        scan(40, 41, _one_hub_cell)
        + "jjj"
        + scan(47, 55, _one_hub_cell)
        + "jj"
        + scan(60, 108, _one_hub_cell)
        + "joojo"
        + scan(114, 128, _one_hub_cell)
    )
    for pc, ops in (
        (3317, scan(37, 125, _short_hub_cell)),
        (3627, one_fill),
        (3949, scan(35, 124, long)),
    ):
        for address, op in enumerate(ops, pc):
            source[address] = _char_for(op, address)


def _write_shared_routes(source: bytearray) -> None:
    """Emit the residue steps, reversible payload reads and glyph palette."""
    # Apply the accumulator mask, negate through all-twos and reload all-ones.
    residue = "jop" + "jojjooo*" + "ojjoojjop" + "ojjj*joj"
    # The two payload passes apply and undo the same crazy involution.
    shadow_walk = "j" * 7 + "ojojoo" + "j" * 4 + "ojo" + "j" * 3 + "ojooj"
    payload = "**" + "o" * 23 + "jpoo" + shadow_walk
    # Printable operands descend cyclically twice for the suffix dispatch.
    palette = "v" * (2 * _ENCODING_PERIOD)
    for pc, ops in (
        (2177, residue),
        (2293, residue),
        (2325, residue),
        (6194, payload),
        (6260, payload),
        (4255, palette),
    ):
        for address, op in enumerate(ops, pc):
            source[address] = _char_for(op, address)


def _write_reset_seed(source: bytearray) -> None:
    """Build the reset constants while C and D walk together."""
    pc = 0

    def place(op: str, glyph: int) -> None:
        nonlocal pc
        # The same printable operand decodes every 94 cells.
        pc += (_char_for(op, pc) - glyph) % _ENCODING_PERIOD
        source[pc] = glyph
        pc += 1

    # Two crazy operations on the cold accumulator leave 80.
    place("p", 55)
    place("p", 53)
    # Preserve the low pointer window; crazy(80, 80) gives all-ones.
    pc = 128
    place("p", 80)
    place("*", 50)
    place("*", 48)
    # The remaining crazy chain restores zero for the first pointer jump.
    for glyph in (126, 116, 115, 111):
        place("p", glyph)


def _write_high_dispatch(source: bytearray, readouts: tuple[int, ...]) -> None:
    """Place the high lookup operand and return glyph in each occupied band."""
    # Primary and spill words occupy the same high bands.
    for high in {_high_cell(word + 1) for word in readouts}:
        source[high] = _char_for("p", high)
        address = high + 1
        if address == 52811:
            # This band retains the higher of its two short-hub glyphs.
            continue
        # In the first band at the top-trit transition, both shadow
        # walks also consume this operand, which leads through the one hub.
        routed = _one_hub_cell if high - 79 == _WORDS // 3 else _short_hub_cell
        source[address] = min(
            raw for op in _ACTIVE if routed((raw := _char_for(op, address)) + 1)
        )


@cache
def _decoder() -> _Decoder:
    """Assemble the decoder and follow its three spill routes from reset."""
    source = bytearray(_char_for("o", k) for k in range(_WORDS))
    for line in (_DATA / "packed-decoder.txt").read_text(encoding="ascii").splitlines():
        origin, ops = line.split()
        lo = int(origin)
        source[lo : lo + len(ops)] = [_char_for(op, lo + i) for i, op in enumerate(ops)]
    _write_reset_seed(source)
    _write_hub_fills(source)
    _write_shared_routes(source)
    _write_guard_approaches(source)
    _write_guard_returns(source)
    # The short seed at the first entry follows its six-cell approach.
    for start in (_PRINTERS[0] + 6, *_PRINTERS[1:]):
        _write_printer(source, start, _SHORT[0])
    readouts = _readouts(16)
    _write_high_dispatch(source, readouts)
    spill_locations = _spill_locations(source, readouts, _SOURCE_OPS)
    used = bytearray(_WORDS)
    locations = []
    for w in readouts:
        bank, residue = divmod(w, _BANK)
        local, slot = spill_locations[residue]
        spill = bank * _BANK + local
        locations.append((w + 1, spill, slot))
        used[w + 1] = 7
        used[spill] |= 1 << slot
    columns: defaultdict[int, list[int]] = defaultdict(list)
    for word, occupied in enumerate(used):
        if occupied:
            columns[(word - 1) % 243].append(word)
    # The jump beside each column marker leads through the short hub.
    for column in columns:
        address = 51032 + 3 * column
        source[address] = next(
            raw
            for op in _ACTIVE
            if _short_hub_cell((raw := _char_for(op, address)) + 1)
        )
    machine = _Machine(source.decode("ascii"), ScriptedIO("0" * 17))
    _at(machine, 4513)
    hubs = tuple(machine.memory[v + 4] + 1 for v in range(127))
    return _Decoder(bytes(source), hubs, tuple(locations), bytes(used), dict(columns))


def _selection(table: str) -> tuple[bytes, tuple[int, ...], int]:
    """Derive the lookup and shared polarity from the navigation answers."""
    from .lookup_request import select  # The constructor shares decoder geometry.

    request = tuple(
        sum(int(table[row]) << bit for bit, row in enumerate(rows)) for rows in _ROWS
    )
    lookup, polarity = select(request)
    return lookup, (0, 1, 2), polarity


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
) -> Iterator[_Column]:
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
            yield _Column(marker, labels)


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


@cache
def _operand_encodings(lookup: bytes, perm: tuple[int, ...]) -> dict[int, _Encodings]:
    """Invert each navigation word's fixed byte-to-answer mapping."""
    decoder = _decoder()
    source = bytearray(decoder.source)
    source[5213:5548] = lookup
    encodings = {}
    for word in _SOURCE_OPS:
        by_answer: dict[int, _Operand] = {}
        restricted: dict[int, _Operand] = {}
        col = (word - 1) % 243
        for column in _marker_labels(source, decoder.hubs, perm, col):
            for op, bits in _operand_patterns(
                source, decoder.hubs, perm, word, column.marker, decoder.occupied[word]
            ):
                operand = _Operand(column, op)
                by_answer.setdefault(bits, operand)
                if (word == _LEFT_OPERAND and op == "<") or (
                    word == _RIGHT_OPERAND and op not in "jv"
                ):
                    restricted.setdefault(bits, operand)
        encodings[word] = _Encodings(by_answer, restricted)
    return encodings


@cache
def _ordinary_columns(lookup: bytes, perm: tuple[int, ...]) -> dict[int, _Column]:
    """Derive an answer alphabet for each column without navigation operands."""
    decoder = _decoder()
    source = bytearray(decoder.source)
    source[5213:5548] = lookup
    restricted = {(word - 1) % 243 for word in _SOURCE_OPS}
    columns: dict[int, _Column] = {}
    for col in decoder.columns.keys() - restricted:
        for column in _marker_labels(source, decoder.hubs, perm, col):
            columns.setdefault(col, column)
    return columns


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


def _coupled_encodings(
    encodings: dict[int, _Encodings], answers: bytearray
) -> tuple[_Operand, _Operand]:
    """Select the first compatible pair without visiting operand pairs."""
    left, right = encodings[_LEFT_OPERAND], encodings[_RIGHT_OPERAND]
    left_bits, right_bits = answers[_LEFT_OPERAND], answers[_RIGHT_OPERAND]
    safe = right.restricted.get(right_bits)
    if safe is None:
        return left.restricted[left_bits], right.by_answer[right_bits]
    first = left.by_answer[left_bits]
    return first, right.by_answer[right_bits] if first.op == "<" else safe


def _write_printer(source: bytearray, pc: int, body: str) -> None:
    """Install the shared lookup entry and output halt around a printer body."""
    for k, op in enumerate("joooj" + body + "<v", pc):
        source[k] = _char_for(op, k)


def _install_layout(
    source: bytearray, lookup: bytes, perm: tuple[int, ...], polarity: int
) -> None:
    """Place the derived lookup and the three straight-line printers."""
    source[5213:5548] = lookup
    for slot, virt in enumerate(perm):
        old = _PRINTERS[slot]
        pc = old + _TAPS[virt] - _TAPS[slot]
        for k in range(old, pc):
            source[k] = _char_for("o", k)
        printer = (_SHORT if virt == 0 else _LONG)[polarity >> slot & 1]
        _write_printer(source, pc, printer)


def _packed_program(table: str) -> str:
    """Emit three primary answers and one spill answer per 15-bit prefix."""
    lookup, perm, polarity = _selection(table)
    decoder = _decoder()
    base, blocks, columns = decoder.source, decoder.locations, decoder.columns
    source = bytearray(base)
    _install_layout(source, lookup, perm, polarity)
    answers = bytearray(_WORDS)
    for i, (primary, spill, slot) in enumerate(blocks):
        a, b, c, d = map(int, table[4 * i : 4 * i + 4])
        answers[primary] = (a + 2 * b + 4 * c) ^ polarity
        answers[spill] |= (d ^ (polarity >> slot & 1)) << slot
    encodings = _operand_encodings(lookup, perm)
    ordinary = _ordinary_columns(lookup, perm)
    operands = {
        word: codes.by_answer[answers[word]] for word, codes in encodings.items()
    }
    operands[_LEFT_OPERAND], operands[_RIGHT_OPERAND] = _coupled_encodings(
        encodings, answers
    )
    selected = {(word - 1) % 243: operand.column for word, operand in operands.items()}
    for col, words in columns.items():
        marker, labels = selected[col] if col in selected else ordinary[col]
        source[51031 + 3 * col] = marker
        for k in words:
            op = operands[k].op if k in operands else labels[answers[k]]
            source[k] = _char_for(op, k)
    return source.decode("ascii")
