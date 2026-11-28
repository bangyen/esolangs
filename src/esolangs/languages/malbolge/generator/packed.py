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
from typing import NamedTuple

from esolangs.languages.malbolge.generator.digits import _readouts
from esolangs.languages.malbolge.generator.isa import (
    _ACTIVE,
    _WORDS,
    _char_for,
)
from esolangs.languages.malbolge.interpreter import _XLAT2, _Machine
from esolangs.runtime.io import ScriptedIO

from .decoder_routes import _write_decoder_routes
from .decoder_tail import _write_decoder_tail
from .emitter import _ENCODING_PERIOD
from .packed_layout import (
    _BANK,
    _HIGH_OPERAND_OFFSET,
    _LONG_HUB,
    _LOOKUP,
    _ONE_HUB,
    _PRINTERS,
    _SHORT_HUB,
    _TAPS,
    _column_marker,
    _high_cell,
    _lookup_base,
    _word_column,
)
from .spill import _spill_locations
from .spill_routes import _write_spill_routes
from .startup_input import _write_input_routes
from .startup_routes import _write_dispatch_setup

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
_SAFE_LEFT_OP = "<"
_SAFE_RIGHT_OPS = "".join(op for op in _ACTIVE if op not in "jv")
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
    safe_with_any_partner: dict[int, _Operand]


type _SelectorGroup = dict[int, list[tuple[int, int]]]


def _at(machine: _Machine, target: int) -> None:
    for _ in range(15000):
        if machine.ip == target:
            return
        if machine.halted:
            break
        machine.step()
    raise AssertionError(f"decoder missed instruction {target}")


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
    """Emit the residue steps and the glyph palette."""
    # Apply the accumulator mask, negate through all-twos and reload all-ones.
    residue = "jop" + "jojjooo*" + "ojjoojjop" + "ojjj*joj"
    # Printable operands descend cyclically twice for the suffix dispatch.
    palette = "v" * (2 * _ENCODING_PERIOD)
    for pc, ops in (
        (2177, residue),
        (2293, residue),
        (2325, residue),
        (4255, palette),
    ):
        for address, op in enumerate(ops, pc):
            source[address] = _char_for(op, address)


def _write_rotation_pair(source: bytearray) -> None:
    """Rotate D133 and D126 three times through the three low returns."""
    pair = "*j" + "o" * (65 - 64) + "j" + "o" * (48 - 47) + "j*"
    ops = (pair + "o" * (133 - 127)) * 2 + pair
    for address, op in enumerate(ops, 1959):
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


def _write_cold_hub_returns(source: bytearray) -> None:
    """Install the hub companions and the cold selector operands."""
    for hub, destinations in (
        (41552, (36, 35)),
        (45926, (45, 121)),
        (54674, (39, 38)),
    ):
        for address, destination in enumerate(destinations, hub):
            source[address] = destination - 1
    # The shifted long-hub return reaches the D71 lookup tap.
    source[54678] = 70 - 1
    source[50220] = min(
        raw for op in _ACTIVE if _short_hub_cell((raw := _char_for(op, 50220)) + 1)
    )
    # The selector and exceptional operands share space with saved pointers.
    for address, op in (
        (29524, "j"),
        (29528, _SOURCE_OPS[29528][0]),
        (_LEFT_OPERAND, _SOURCE_OPS[_LEFT_OPERAND][0]),
        (_RIGHT_OPERAND, "p"),
        (59035, _SOURCE_OPS[59035][0]),
        (59036, _SOURCE_OPS[59036][-1]),
    ):
        source[address] = _char_for(op, address)


def _write_high_dispatch(source: bytearray, readouts: tuple[int, ...]) -> None:
    """Place the high lookup operand and return glyph in each occupied band."""
    # Primary and spill words occupy the same high bands.
    for high in {_high_cell(word + 1) for word in readouts}:
        source[high] = _char_for("p", high)
        address = high + 1
        # One band uses the higher of its two short-hub glyphs.
        choose = max if address == 52811 else min
        # In the first band at the top-trit transition, both shadow
        # walks also consume this operand, which leads through the one hub.
        routed = (
            _one_hub_cell
            if high - _HIGH_OPERAND_OFFSET == _WORDS // 3
            else _short_hub_cell
        )
        source[address] = choose(
            raw for op in _ACTIVE if routed((raw := _char_for(op, address)) + 1)
        )


def _write_fixed_decoder(source: bytearray) -> None:
    """Install the startup, routes, and cold printer seeds."""
    _write_reset_seed(source)
    _write_input_routes(source)
    _write_dispatch_setup(source)
    _write_hub_fills(source)
    _write_shared_routes(source)
    _write_rotation_pair(source)
    _write_cold_hub_returns(source)
    _write_decoder_routes(source)
    _write_spill_routes(source)
    _write_decoder_tail(source)
    # The short seed at the first entry follows its six-cell approach.
    for start in (_PRINTERS[0] + 6, *_PRINTERS[1:]):
        _write_printer(source, start, _SHORT[0])


def _allocate_payloads(
    source: bytearray, readouts: tuple[int, ...]
) -> tuple[tuple[tuple[int, int, int], ...], bytes, dict[int, list[int]]]:
    """Place spill markers and collect the occupied slots and columns."""
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
            columns[_word_column(word)].append(word)
    return tuple(locations), bytes(used), dict(columns)


def _write_column_returns(source: bytearray, columns: dict[int, list[int]]) -> None:
    # The jump beside each column marker leads through the short hub.
    for column in columns:
        address = _column_marker(column) + 1
        source[address] = next(
            raw
            for op in _ACTIVE
            if _short_hub_cell((raw := _char_for(op, address)) + 1)
        )


@cache
def _decoder() -> _Decoder:
    """Assemble the decoder and follow its three spill routes from reset."""
    source = bytearray(_char_for("o", k) for k in range(_WORDS))
    _write_fixed_decoder(source)
    readouts = _readouts(16)
    _write_high_dispatch(source, readouts)
    locations, occupied, columns = _allocate_payloads(source, readouts)
    _write_column_returns(source, columns)
    machine = _Machine(source.decode("ascii"), ScriptedIO("0" * 17))
    _at(machine, _PRINTERS[0])
    hubs = tuple(machine.memory[v + 4] + 1 for v in range(127))
    return _Decoder(bytes(source), hubs, locations, occupied, columns)


def _selection(table: str) -> tuple[bytes, int]:
    """Derive the lookup and shared polarity from the navigation answers."""
    from .lookup_request import select  # The constructor shares decoder geometry.

    request = tuple(
        sum(int(table[row]) << bit for bit, row in enumerate(rows)) for rows in _ROWS
    )
    return select(request)


def _pattern(
    source: bytes | bytearray,
    hubs: tuple[int, ...],
    k: int,
    raw: int,
    marker: int,
    used: int,
) -> int | None:
    """Read the requested slots, or return None if a tap cannot supply its bit."""
    key = _lookup_base(k, raw, marker)
    bits = 0
    for slot, tap in enumerate(_TAPS):
        if used >> slot & 1:
            hub = hubs[source[key + tap]]
            if hub == _ONE_HUB:
                bits |= 1 << slot
            elif hub != _SHORT_HUB and (not slot or hub != _LONG_HUB):
                return None
    return bits


def _marker_labels(
    source: bytes | bytearray, hubs: tuple[int, ...], col: int
) -> Iterator[_Column]:
    """Yield column markers with all eight ordinary labels."""
    # Advancing one column period subtracts that period from raw and high modulo 94.
    # Their difference, and thus the ordinary label, depends only on the column.
    rep = col + 1
    for marker_op in _ACTIVE:
        marker = _char_for(marker_op, _column_marker(col))
        if marker < 83:
            continue
        labels = {}
        for op in _ACTIVE:
            label = _pattern(source, hubs, rep, _char_for(op, rep), marker, 7)
            if label is None or label in labels:
                break
            labels[label] = op
        else:
            yield _Column(marker, labels)


def _operand_patterns(
    source: bytes | bytearray,
    hubs: tuple[int, ...],
    word: int,
    marker: int,
    used: int,
) -> Iterator[tuple[str, int]]:
    """Yield the patterns of legal operands at a navigation word."""
    for op in _SOURCE_OPS[word]:
        raw = _char_for(op, word)
        if 29524 <= word <= 29527:
            raw = ord(_XLAT2[raw - 33])
        bits = _pattern(source, hubs, word, raw, marker, used)
        if bits is not None:
            yield op, bits


@cache
def _lookup_image(lookup: bytes) -> bytes:
    """Overlay a lookup on the decoder for both column encoders."""
    source = _decoder().source
    return b"".join((source[: _LOOKUP.start], lookup, source[_LOOKUP.stop :]))


@cache
def _operand_encodings(lookup: bytes) -> dict[int, _Encodings]:
    """Invert each navigation word's fixed byte-to-answer mapping."""
    decoder = _decoder()
    source = _lookup_image(lookup)
    encodings = {}
    for word in _SOURCE_OPS:
        by_answer: dict[int, _Operand] = {}
        safe_with_any_partner: dict[int, _Operand] = {}
        col = _word_column(word)
        for column in _marker_labels(source, decoder.hubs, col):
            for op, bits in _operand_patterns(
                source, decoder.hubs, word, column.marker, decoder.occupied[word]
            ):
                operand = _Operand(column, op)
                by_answer.setdefault(bits, operand)
                safe_left = word == _LEFT_OPERAND and op == _SAFE_LEFT_OP
                safe_right = word == _RIGHT_OPERAND and op in _SAFE_RIGHT_OPS
                if safe_left or safe_right:
                    safe_with_any_partner.setdefault(bits, operand)
        encodings[word] = _Encodings(by_answer, safe_with_any_partner)
    return encodings


@cache
def _ordinary_columns(lookup: bytes) -> dict[int, _Column]:
    """Derive an answer alphabet for each column without navigation operands."""
    decoder = _decoder()
    source = _lookup_image(lookup)
    restricted = {_word_column(word) for word in _SOURCE_OPS}
    columns: dict[int, _Column] = {}
    for col in decoder.columns.keys() - restricted:
        for column in _marker_labels(source, decoder.hubs, col):
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
    safe_right = right.safe_with_any_partner.get(right_bits)
    if safe_right is None:
        safe_left = left.safe_with_any_partner[left_bits]
        return safe_left, right.by_answer[right_bits]
    first_left = left.by_answer[left_bits]
    if first_left.op == _SAFE_LEFT_OP:
        return first_left, right.by_answer[right_bits]
    return first_left, safe_right


def _write_printer(source: bytearray, pc: int, body: str) -> None:
    """Install the shared lookup entry and output halt around a printer body."""
    for k, op in enumerate("joooj" + body + "<v", pc):
        source[k] = _char_for(op, k)


def _install_printers(source: bytearray, polarity: int) -> None:
    """Install the three printers for the selected polarity."""
    for slot, pc in enumerate(_PRINTERS):
        printer = (_SHORT if slot == 0 else _LONG)[polarity >> slot & 1]
        _write_printer(source, pc, printer)


def _pack_answers(table: str, decoder: _Decoder, polarity: int) -> bytearray:
    """Pack three primary bits and one spill bit per 15-bit prefix."""
    answers = bytearray(_WORDS)
    for i, (primary, spill, slot) in enumerate(decoder.locations):
        a, b, c, d = map(int, table[4 * i : 4 * i + 4])
        answers[primary] = (a + 2 * b + 4 * c) ^ polarity
        answers[spill] |= (d ^ (polarity >> slot & 1)) << slot
    return answers


def _packed_program(table: str) -> str:
    """Emit the packed decoder with the supplied truth table."""
    lookup, polarity = _selection(table)
    decoder = _decoder()
    answers = _pack_answers(table, decoder, polarity)
    source = bytearray(_lookup_image(lookup))
    _install_printers(source, polarity)
    encodings = _operand_encodings(lookup)
    ordinary = _ordinary_columns(lookup)
    left, right = _coupled_encodings(encodings, answers)
    operands = {
        word: codes.by_answer[answers[word]]
        for word, codes in encodings.items()
        if word not in (_LEFT_OPERAND, _RIGHT_OPERAND)
    }
    operands.update({_LEFT_OPERAND: left, _RIGHT_OPERAND: right})
    selected = {
        _word_column(word): operand.column for word, operand in operands.items()
    }
    for col, words in decoder.columns.items():
        marker, labels = selected[col] if col in selected else ordinary[col]
        source[_column_marker(col)] = marker
        for k in words:
            op = operands[k].op if k in operands else labels[answers[k]]
            source[k] = _char_for(op, k)
    return source.decode("ascii")
