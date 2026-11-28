"""Describe the packed lookup from printer taps and legal decoder glyphs."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from esolangs.languages.malbolge.generator.isa import _ACTIVE, _char_for
from esolangs.languages.malbolge.generator.lookup_domains import _glyph_domains
from esolangs.languages.malbolge.generator.packed import _SOURCE_OPS, _decoder
from esolangs.languages.malbolge.interpreter import _XLAT2

from .packed_layout import (
    _COLUMN_COUNT,
    _SHORT_HUB,
    _TAPS,
    _column_marker,
    _lookup_base,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

type Role = tuple[int, str]
type Reads = tuple[int, ...]
type Alphabet = tuple[Reads, ...]
_ORDINARY = {0: "*/ov", 2: "/ipv"}
_NAVIGATION = (0, "j")
_NAVIGATION_WORDS = (59035, 59036, 59037)


class Contact(NamedTuple):
    """One source instruction's observable lookup addresses."""

    role: Role
    op: str
    reads: Reads


class Geometry(NamedTuple):
    """Address domains, ordinary role taps and navigation contacts."""

    glyphs: dict[int, dict[int, int]]
    alphabets: dict[Role, Alphabet]
    mandatory_ones: dict[Role, set[int]]
    navigation: dict[int, tuple[Contact, ...]]


def _markers(column: int) -> Iterator[tuple[Role, int]]:
    for op in _ACTIVE:
        glyph = _char_for(op, _column_marker(column))
        lane = (2 - glyph) % 3
        if glyph >= 83 and lane in _ORDINARY:
            yield (lane, op), glyph


def _tap(word: int, raw: int, marker: int, channel: int) -> int:
    return _lookup_base(word, raw, marker) + _TAPS[channel]


def _alphabet(
    column: int,
    marker: int,
    glyphs: Mapping[int, dict[int, int]],
    hubs: tuple[int, ...],
) -> Alphabet | None:
    word = column + 1
    reads = tuple(
        tuple(_tap(word, _char_for(op, word), marker, i) for i in range(3))
        for op in _ACTIVE
    )
    if not all(
        all(glyphs[a] for a in row)
        and (1 in glyphs[row[0]] or hubs[glyphs[row[0]].get(0, 0)] == _SHORT_HUB)
        for row in reads
    ):
        return None
    return tuple(zip(*reads, strict=True))


def geometry() -> Geometry:
    """Return the exact nine-role geometry used by the selector proof."""
    decoder = _decoder()
    glyphs = _glyph_domains(decoder, _SOURCE_OPS)
    alphabets: dict[Role, Alphabet] = {}
    mandatory: dict[Role, set[int]] = {}
    navigation: dict[int, tuple[Contact, ...]] = {}
    navigation_columns = {(word - 1) % _COLUMN_COUNT for word in _NAVIGATION_WORDS}
    selected = {(lane, role) for lane, roles in _ORDINARY.items() for role in roles}
    for column in decoder.columns:
        covered = False
        for role, marker in _markers(column):
            if role not in selected and (
                role != _NAVIGATION or column not in navigation_columns
            ):
                continue
            shape = _alphabet(column, marker, glyphs, decoder.hubs)
            if shape is None:
                continue
            covered |= role in selected
            alphabets[role] = shape
            mandatory.setdefault(role, set()).update(
                a for a in shape[0] if decoder.hubs[glyphs[a].get(0, 0)] != _SHORT_HUB
            )
        assert covered
    for word, allowed in _SOURCE_OPS.items():
        column = (word - 1) % _COLUMN_COUNT
        slots = tuple(i for i in range(3) if decoder.occupied[word] >> i & 1)
        contacts = []
        for role, marker in _markers(column):
            if (
                role not in alphabets
                or _alphabet(column, marker, glyphs, decoder.hubs) is None
            ):
                continue
            for op in allowed:
                raw = _char_for(op, word)
                if 29524 <= word <= 29527:
                    raw = ord(_XLAT2[raw - 33])
                reads = tuple(_tap(word, raw, marker, i) for i in slots)
                if all(glyphs[address] for address in reads):
                    contacts.append(Contact(role, op, reads))
        navigation[word] = tuple(contacts)
    return Geometry(glyphs, alphabets, mandatory, navigation)
