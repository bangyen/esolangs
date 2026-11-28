"""Build a packed lookup and its polarity directly from the requested answers."""

from __future__ import annotations

from collections import Counter
from functools import cache
from typing import NamedTuple

from esolangs.languages.malbolge.generator.isa import _ACTIVE
from esolangs.languages.malbolge.generator.packed import (
    _LEFT_OPERAND,
    _RIGHT_OPERAND,
    _SAFE_LEFT_OP,
    _SAFE_RIGHT_OPS,
    _SOURCE_OPS,
    _decoder,
    _selector_groups,
)

from .lookup_diagram import Checkpoint, Diagram
from .lookup_elimination import Factor, eliminate, min_fill, reconstruct
from .lookup_geometry import Geometry, geometry
from .lookup_independent import (
    AlphabetTable,
    Requirements,
    Variable,
    _compile_check,
    _coordinate,
    _lift,
    _short_zero,
    alphabet_table,
    fixed_colors,
    independent_lookup,
    scopes,
)
from .packed_layout import (
    _LOOKUP,
    _ONE_HUB,
)

_OUTPUT = 4
_PAIR_BRANCH = (5, 0)
_PHASE_BLOCKS = (3, 12, 48, 64)
_NODE_LIMIT = 400_000
type RequestWord = tuple[int, int, str]
type SelectorRequest = dict[int, dict[int, int]]


class Prepared(NamedTuple):
    """Reusable ordinary factors and all possible selector contacts."""

    geo: Geometry
    checkpoint: Checkpoint
    fixed: dict[Variable, int]
    order: tuple[Variable, ...]
    position: dict[Variable, int]
    shared: tuple[Factor, ...]
    alphabet_tables: tuple[AlphabetTable, ...]
    targets: dict[int, frozenset[int]]
    patterns: dict[RequestWord, int]
    groups: tuple[dict[int, list[tuple[int, int]]], ...]


def _word_requirements(geo: Geometry, word: int, answer: int, ops: str) -> Requirements:
    occupied = _decoder().occupied[word]
    slots = tuple(slot for slot in range(3) if occupied >> slot & 1)
    return tuple(
        tuple(
            (_coordinate(contact.role[0], address), answer >> slot & 1)
            for slot, address in zip(slots, contact.reads, strict=True)
        )
        for contact in geo.navigation[word]
        if contact.op in ops
        and all(
            (answer >> slot & 1) in geo.glyphs[address]
            and (slot != 0 or answer & 1 or _short_zero(geo, address))
            for slot, address in zip(slots, contact.reads, strict=True)
        )
    )


def _support(
    requirements: Requirements, fixed: dict[Variable, int]
) -> frozenset[Variable]:
    return frozenset(a for row in requirements for a, _ in row) - fixed.keys()


def selector_axes(
    groups: tuple[dict[int, list[tuple[int, int]]], ...],
) -> tuple[int, tuple[int, ...], dict[int, dict[int, int]]]:
    """Number the projected bits and report the pinned right operand slots."""
    width = 0
    pin = []
    axes: dict[int, dict[int, int]] = {}
    for group in groups:
        by_row = sorted(
            (row, word, slot)
            for word, entries in group.items()
            for slot, row in entries
        )
        for _, word, slot in by_row:
            if word == _RIGHT_OPERAND:
                pin.append(slot)
            else:
                axes.setdefault(word, {})[slot] = width
                width += 1
    return width, tuple(sorted(pin)), axes


@cache
def _independent() -> bytes:
    return independent_lookup(geometry())


@cache
def prepare(physical: int | None = None) -> Prepared:
    """Compile the decoder's common factors once without storing lookup bytes."""
    geo = geometry()
    decoder = _decoder()
    independent = _independent()
    known = {
        _coordinate(a % 3, a): int(
            decoder.hubs[independent[a - _LOOKUP.start]] == _ONE_HUB
        )
        for a, domain in geo.glyphs.items()
        if a % 3 != 1 and domain
    }
    fixed = fixed_colors(geo)
    roles = scopes(geo, fixed)
    groups = _selector_groups()
    selector = {word for group in groups for word in group}
    width, _, outputs = selector_axes(groups)
    checks: list[Requirements] = []
    patterns: dict[RequestWord, Requirements] = {}
    targets: dict[int, frozenset[Variable]] = {}
    for word in _SOURCE_OPS:
        occupied = decoder.occupied[word]
        allowed = (
            (_ACTIVE, _SAFE_LEFT_OP)
            if word == _LEFT_OPERAND
            else (_ACTIVE, _SAFE_RIGHT_OPS)
            if word == _RIGHT_OPERAND
            else (_ACTIVE,)
        )
        for answer in range(8):
            if answer & occupied != answer:
                continue
            if physical is not None and word == _RIGHT_OPERAND and answer != physical:
                continue
            for ops in allowed:
                reqs = _word_requirements(geo, word, answer, ops)
                if word in selector:
                    patterns[word, answer, ops] = reqs
                else:
                    lane = min(
                        row[0][0][0]
                        for row in reqs
                        if all(known[a] == bit for a, bit in row)
                    )
                    checks.append(tuple(row for row in reqs if row[0][0][0] == lane))
    for word in selector:
        selector_scope = frozenset().union(
            *(
                _support(req, fixed)
                for (owner, _, _), req in patterns.items()
                if owner == word
            )
        )
        if word in (_LEFT_OPERAND, _RIGHT_OPERAND):
            selector_scope |= {_PAIR_BRANCH}
        if physical is not None:
            selector_scope |= {
                (_OUTPUT, axis) for axis in outputs.get(word, {}).values()
            }
        targets[word] = selector_scope

    navigation_scopes = tuple(_support(req, fixed) for req in checks)
    uses = Counter(
        a
        for scope in (*roles.values(), *navigation_scopes, *targets.values())
        for a in scope
    )
    ordinary_scopes = tuple(
        frozenset(a for a in scope if uses[a] > 1) for scope in roles.values()
    )
    scopes_all = (*ordinary_scopes, *navigation_scopes, *targets.values())
    axes = tuple(sorted(set().union(*scopes_all)))
    axis_index = {a: i for i, a in enumerate(axes)}
    deferred = frozenset(i for i, axis in enumerate(axes) if axis[0] == _OUTPUT)
    order = tuple(
        axes[i]
        for i in min_fill(
            (frozenset(axis_index[a] for a in scope) for scope in scopes_all), deferred
        )
        if i not in deferred
    )
    if deferred:
        order += tuple((_OUTPUT, axis) for axis in reversed(range(width)))
    position = {a: i for i, a in enumerate(order)}
    arena = Diagram(len(order), _NODE_LIMIT)
    shared = []
    tables = []
    for role, scope in roles.items():
        interface = tuple(
            sorted(scope & position.keys(), key=position.__getitem__, reverse=True)
        )
        private = tuple(sorted(scope - position.keys()))
        table = alphabet_table(geo, role, fixed, interface, private)
        reduced = table.permitted
        for i in reversed(range(len(interface), len(interface) + len(private))):
            reduced = (reduced | (reduced >> (1 << i))) & ((1 << (1 << i)) - 1)
        axes_for_role = tuple(position[a] for a in interface)
        shared.append(
            Factor(frozenset(axes_for_role), arena.compile_bits(axes_for_role, reduced))
        )
        tables.append(table)
    for req, scope in zip(checks, navigation_scopes, strict=True):
        shared.append(
            Factor(
                frozenset(position[a] for a in scope),
                _compile_check(arena, req, position, fixed),
            )
        )
    compiled = {
        key: _compile_check(arena, req, position, fixed)
        for key, req in patterns.items()
    }
    return Prepared(
        geo,
        arena.snapshot(),
        fixed,
        order,
        position,
        tuple(shared),
        tuple(tables),
        {
            word: frozenset(position[a] for a in scope)
            for word, scope in targets.items()
        },
        compiled,
        groups,
    )


def contact_relation(arena: Diagram, prepared: Prepared, word: int, answer: int) -> int:
    """Combine unrestricted contacts with the selected side of the joint guard."""
    term = prepared.patterns.get((word, answer, _ACTIVE), 0)
    if word in (_LEFT_OPERAND, _RIGHT_OPERAND):
        restricted = _SAFE_LEFT_OP if word == _LEFT_OPERAND else _SAFE_RIGHT_OPS
        branch = arena.literal(
            prepared.position[_PAIR_BRANCH], int(word == _RIGHT_OPERAND)
        )
        term = arena.combine(
            arena.combine(term, branch),
            prepared.patterns[word, answer, restricted],
            union=True,
        )
    return term


def _requested_relation(
    arena: Diagram,
    prepared: Prepared,
    word: int,
    requested: dict[int, int],
    phase_block: int,
) -> int:
    root = 0
    for answer in range(8):
        key = word, answer, _ACTIVE
        if key not in prepared.patterns:
            continue
        phases = sum(
            1 << phase
            for phase in range(7)
            if phase_block >> phase & 1
            and all(
                ((answer ^ phase) >> slot & 1) == bit for slot, bit in requested.items()
            )
        )
        if not phases:
            continue
        term = contact_relation(arena, prepared, word, answer)
        root = arena.combine(root, arena.combine(term, phases), union=True)
    return root


def emit(prepared: Prepared, assignment: int) -> bytes:
    """Lift projected colors and materialize the native lookup frame."""
    values = {
        **prepared.fixed,
        **{a: assignment >> i & 1 for i, a in enumerate(prepared.order)},
    }
    for table in prepared.alphabet_tables:
        _lift(table, values)
    source = _decoder().source
    return bytes(
        options[values.get(_coordinate(a % 3, a), 0)]
        if options and a % 3 != 1
        else source[a]
        for a, options in prepared.geo.glyphs.items()
    )


def unpack_request(request: tuple[int, ...]) -> SelectorRequest:
    """Decode logical selector bits by operand word and slot."""
    return {
        word: {slot: answer >> bit & 1 for slot, bit in entries}
        for group, answer in zip(_selector_groups(), request, strict=True)
        for word, entries in group.items()
    }


def _select_fast(requested: SelectorRequest) -> tuple[bytes, int]:
    """Project the compatible polarity mask and reconstruct its first layout."""
    prepared = prepare()
    arena = Diagram(len(prepared.order), _NODE_LIMIT)
    for block in _PHASE_BLOCKS:
        arena.restore(prepared.checkpoint)
        factors = [
            *prepared.shared,
            *(
                Factor(
                    scope,
                    _requested_relation(arena, prepared, word, requested[word], block),
                )
                for word, scope in prepared.targets.items()
            ),
        ]
        witness = eliminate(arena, factors, range(len(prepared.order)))
        if witness.phases:
            phase = (witness.phases & -witness.phases).bit_length() - 1
            assignment = reconstruct(arena, witness, phase)
            return emit(prepared, assignment), phase
    raise AssertionError("selector coverage is incomplete")


def select(request: tuple[int, ...]) -> tuple[bytes, int]:
    """Derive a compatible layout, using the bounded projection on arena overflow."""
    requested = unpack_request(request)
    try:
        return _select_fast(requested)
    except OverflowError:
        from .lookup_projection import select_bounded

    return select_bounded(requested)
