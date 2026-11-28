"""Construct a request-independent allocation of navigation patterns."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from itertools import product
from typing import NamedTuple

from esolangs.languages.malbolge.generator.packed import _decoder, _operand_encodings

from .lookup_diagram import ALL_PHASES, Diagram
from .lookup_elimination import Factor, eliminate, min_fill, reconstruct
from .lookup_geometry import Geometry, Role
from .packed_layout import (
    _SHORT_HUB,
)

type Variable = tuple[int, int]
type Clause = tuple[tuple[Variable, int], ...]
type Requirements = tuple[Clause, ...]


class AlphabetTable(NamedTuple):
    """A role's truth bitset ordered by its interface and private variables."""

    interface: tuple[Variable, ...]
    private: tuple[Variable, ...]
    permitted: int


def _coordinate(lane: int, address: int) -> Variable:
    return lane, address % 94


def fixed_colors(geo: Geometry) -> dict[Variable, int]:
    """Project the single-glyph physical domains onto periodic color variables."""
    return {
        _coordinate(a % 3, a): next(iter(allowed))
        for a, allowed in geo.glyphs.items()
        if a % 3 != 1 and len(allowed) == 1
    }


def scopes(
    geo: Geometry, fixed: dict[Variable, int]
) -> dict[Role, frozenset[Variable]]:
    """Collect variable colors used by each ordinary alphabet."""
    return {
        role: frozenset(_coordinate(role[0], a) for row in alphabet for a in row)
        - fixed.keys()
        for role, alphabet in geo.alphabets.items()
    }


def _short_zero(geo: Geometry, address: int) -> bool:
    return _decoder().hubs[geo.glyphs[address].get(0, 0)] == _SHORT_HUB


def contacts(geo: Geometry, word: int, bits: int) -> Requirements:
    """Expose native ways to read a particular occupied answer pattern."""
    used = _decoder().occupied[word]
    slots = tuple(slot for slot in range(3) if used >> slot & 1)
    result = []
    for entry in geo.navigation[word]:
        if word == 29524 and entry.role[0] != 2:
            continue
        if all(
            (bits >> slot & 1) in geo.glyphs[address]
            and (slot != 0 or bits & 1 or _short_zero(geo, address))
            for slot, address in zip(slots, entry.reads, strict=True)
        ):
            result.append(
                tuple(
                    (_coordinate(entry.role[0], address), bits >> slot & 1)
                    for slot, address in zip(slots, entry.reads, strict=True)
                )
            )
    return tuple(result)


def _missing(geo: Geometry, word: int, role: Role) -> tuple[tuple[Variable, ...], ...]:
    """Each high navigation word reads a proper subset of the ordinary alphabet."""
    lane, _ = role
    atlas = dict.fromkeys(
        tuple(_coordinate(lane, a) for a in row)
        for row in zip(*geo.alphabets[role], strict=True)
    )
    for entry in geo.navigation[word]:
        if entry.role == role:
            assert _short_zero(geo, entry.reads[0])
            del atlas[tuple(_coordinate(lane, a) for a in entry.reads)]
    return tuple(atlas)


def requirements(geo: Geometry) -> tuple[Requirements, ...]:
    """Choose one lane at the encrypted word and disjoint omissions at high words."""
    checks = [contacts(geo, 29524, answer) for answer in range(8)]
    checks.extend(contacts(geo, 41391, answer) for answer in (0, 2))
    for word in (59035, 59036, 59037):
        for left, right in product(
            _missing(geo, word, (0, "j")), _missing(geo, word, (2, "/"))
        ):
            checks.append(
                tuple(
                    ((a, bit), (b, 1 - bit))
                    for a, b in zip(left, right, strict=True)
                    for bit in (0, 1)
                )
            )
    return tuple(checks)


def alphabet_table(
    geo: Geometry,
    role: Role,
    fixed: dict[Variable, int],
    interface: tuple[Variable, ...],
    private: tuple[Variable, ...],
) -> AlphabetTable:
    """Compile the valid permutations as a bitset without choosing a label structure."""
    lane, _ = role
    size = len(interface) + len(private)
    full = (1 << (1 << size)) - 1
    values = {
        item: full // ((1 << (1 << i)) + 1) << (1 << i)
        for i, item in enumerate(interface + private)
    }
    values.update({item: full if bit else 0 for item, bit in fixed.items()})
    rows = tuple(
        tuple(values[_coordinate(lane, address)] for address in row)
        for row in zip(*geo.alphabets[role], strict=True)
    )
    allowed = full
    for i, first in enumerate(rows):
        for second in rows[:i]:
            difference = 0
            for a, b in zip(first, second, strict=True):
                difference |= a ^ b
            allowed &= difference
    for address in geo.mandatory_ones[role]:
        allowed &= values[_coordinate(lane, address)]
    return AlphabetTable(interface, private, allowed)


def _compile_check(
    arena: Diagram,
    clauses: Requirements,
    position: dict[Variable, int],
    fixed: dict[Variable, int],
) -> int:
    result = 0
    for clause in clauses:
        term = ALL_PHASES
        for coordinate, bit in clause:
            if coordinate in fixed:
                literal = ALL_PHASES if fixed[coordinate] == bit else 0
            else:
                literal = arena.literal(position[coordinate], bit)
            term = arena.combine(term, literal)
        result = arena.combine(result, term, union=True)
    return result


def alphabet_factor(
    arena: Diagram,
    geo: Geometry,
    role: Role,
    fixed: dict[Variable, int],
    scope: frozenset[Variable],
    position: dict[Variable, int],
) -> tuple[Factor, AlphabetTable]:
    """Project out private colors and retain their table for reconstruction."""
    interface = tuple(
        sorted(scope & position.keys(), key=position.__getitem__, reverse=True)
    )
    private = tuple(sorted(scope - position.keys()))
    table = alphabet_table(geo, role, fixed, interface, private)
    reduced = table.permitted
    for i in reversed(range(len(interface), len(interface) + len(private))):
        reduced = (reduced | (reduced >> (1 << i))) & ((1 << (1 << i)) - 1)
    names = tuple(position[a] for a in interface)
    return Factor(frozenset(names), arena.compile_bits(names, reduced)), table


def _lift(table: AlphabetTable, values: dict[Variable, int]) -> None:
    index = sum(values.get(a, 0) << i for i, a in enumerate(table.interface))
    stride = 1 << len(table.interface)
    periodic = ((1 << (stride * (1 << len(table.private)))) - 1) // ((1 << stride) - 1)
    matching = table.permitted & (periodic << index)
    assert matching
    assignment = (matching & -matching).bit_length() - 1
    for i, coordinate in enumerate(table.private, len(table.interface)):
        values[coordinate] = assignment >> i & 1


def render_lookup(
    geo: Geometry,
    tables: Iterable[AlphabetTable],
    fixed: dict[Variable, int],
    order: tuple[Variable, ...],
    assignment: int,
) -> bytes:
    """Recover private colors and write their glyphs into the lookup frame."""
    values = {**fixed, **{a: assignment >> i & 1 for i, a in enumerate(order)}}
    for table in tables:
        _lift(table, values)
    source = _decoder().source
    return bytes(
        options[values.get(_coordinate(a % 3, a), 0)]
        if options and a % 3 != 1
        else source[a]
        for a, options in geo.glyphs.items()
    )


def independent_lookup(geo: Geometry) -> bytes:
    """Render a deterministic lookup that supplies every independent pattern."""
    fixed = fixed_colors(geo)
    role_scopes = scopes(geo, fixed)
    checks = requirements(geo)
    check_scopes = tuple(
        frozenset(coordinate for clause in item for coordinate, _ in clause)
        - fixed.keys()
        for item in checks
    )
    uses = Counter(a for scope in (*role_scopes.values(), *check_scopes) for a in scope)
    scopes_with_interface = tuple(
        frozenset(a for a in scope if uses[a] > 1) for scope in role_scopes.values()
    )
    coordinates = tuple(sorted(set().union(*scopes_with_interface, *check_scopes)))
    indices = {a: i for i, a in enumerate(coordinates)}
    order = min_fill(
        frozenset(indices[a] for a in scope)
        for scope in (*scopes_with_interface, *check_scopes)
    )
    ordered = tuple(coordinates[i] for i in order)
    position = {a: i for i, a in enumerate(ordered)}
    arena = Diagram(len(ordered), 400_000)
    factors = []
    tables = []
    for role, scope in role_scopes.items():
        factor, table = alphabet_factor(arena, geo, role, fixed, scope, position)
        factors.append(factor)
        tables.append(table)
    for check, scope in zip(checks, check_scopes, strict=True):
        factors.append(
            Factor(
                frozenset(position[a] for a in scope),
                _compile_check(arena, check, position, fixed),
            )
        )
    proof = eliminate(arena, factors, range(len(ordered)))
    assert proof.phases == ALL_PHASES
    result = reconstruct(arena, proof, 0)
    output = render_lookup(geo, tables, fixed, ordered, result)
    decoder = _decoder()
    verified = _operand_encodings(output)
    assert all(
        len(verified[word].by_answer) == 1 << decoder.occupied[word].bit_count()
        for word in (29524, 41391, 59035, 59036, 59037)
    )
    return output
