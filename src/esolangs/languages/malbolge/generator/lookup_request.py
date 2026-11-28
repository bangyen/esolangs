"""Build a packed lookup and its polarity directly from the requested answers."""

from __future__ import annotations

from functools import cache
from itertools import batched
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

from .lookup_diagram import PHASES, Checkpoint, Diagram
from .lookup_elimination import Factor, eliminate, reconstruct
from .lookup_geometry import Geometry, geometry
from .lookup_independent import (
    AlphabetTable,
    Requirements,
    Variable,
    _compile_check,
    _coordinate,
    alphabet_factor,
    contact_clause,
    fixed_colors,
    independent_lookup,
    order_colors,
    render_lookup,
    scopes,
    shared_alphabet_scopes,
)
from .packed_layout import (
    _LOOKUP,
    _ONE_HUB,
)

_OUTPUT = 4
_PAIR_BRANCH = (5, 0)
_PAIR_GUARDS = {_LEFT_OPERAND: (_SAFE_LEFT_OP, 0), _RIGHT_OPERAND: (_SAFE_RIGHT_OPS, 1)}
_PHASE_BLOCKS = tuple(
    sum(1 << phase for phase in block) for block in batched(PHASES, 2)
)
_NODE_LIMIT = 400_000


class SelectorBits(NamedTuple):
    """The occupied request slots and their logical bit values."""

    mask: int
    value: int


type SelectorRequest = dict[int, SelectorBits]


class SelectorWord(NamedTuple):
    """One selector's factor scope and contact roots by answer and opcode set."""

    scope: frozenset[int]
    answers: dict[int, dict[str, int]]


class Prepared(NamedTuple):
    """Reusable ordinary factors and all possible selector contacts."""

    geo: Geometry
    checkpoint: Checkpoint
    fixed: dict[Variable, int]
    order: tuple[Variable, ...]
    position: dict[Variable, int]
    physical: int | None
    color_count: int
    shared: tuple[Factor, ...]
    alphabet_tables: tuple[AlphabetTable, ...]
    selectors: dict[int, SelectorWord]


def _word_requirements(geo: Geometry, word: int, answer: int, ops: str) -> Requirements:
    return tuple(
        clause
        for contact in geo.navigation[word]
        if contact.op in ops
        and (clause := contact_clause(geo, contact, answer)) is not None
    )


def _support(
    requirements: Requirements, fixed: dict[Variable, int]
) -> frozenset[Variable]:
    return frozenset(a for row in requirements for a, _ in row) - fixed.keys()


@cache
def selector_axes() -> tuple[int, tuple[int, ...], dict[int, dict[int, int]]]:
    """Number the projected bits and report the pinned right operand slots."""
    width = 0
    pin = []
    axes: dict[int, dict[int, int]] = {}
    for group in _selector_groups():
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
    width, _, outputs = selector_axes()
    checks: list[Requirements] = []
    patterns: dict[int, dict[int, dict[str, Requirements]]] = {
        word: {} for word in _SOURCE_OPS if word in selector
    }
    targets: dict[int, frozenset[Variable]] = {}
    for word in _SOURCE_OPS:
        occupied = decoder.occupied[word]
        guard = _PAIR_GUARDS.get(word)
        allowed = (_ACTIVE,) if guard is None else (_ACTIVE, guard[0])
        for answer in range(8):
            if answer & occupied != answer:
                continue
            if physical is not None and word == _RIGHT_OPERAND and answer != physical:
                continue
            for ops in allowed:
                reqs = _word_requirements(geo, word, answer, ops)
                if word in selector:
                    patterns[word].setdefault(answer, {})[ops] = reqs
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
                for contacts in patterns[word].values()
                for req in contacts.values()
            )
        )
        if word in _PAIR_GUARDS:
            selector_scope |= {_PAIR_BRANCH}
        if physical is not None:
            selector_scope |= {
                (_OUTPUT, axis) for axis in outputs.get(word, {}).values()
            }
        targets[word] = selector_scope

    navigation_scopes = tuple(_support(req, fixed) for req in checks)
    ordinary_scopes = shared_alphabet_scopes(
        roles, (*navigation_scopes, *targets.values())
    )
    scopes_all = (*ordinary_scopes, *navigation_scopes, *targets.values())
    output_order = (
        tuple((_OUTPUT, axis) for axis in reversed(range(width)))
        if physical is not None
        else ()
    )
    order = order_colors(scopes_all, output_order)
    position = {a: i for i, a in enumerate(order)}
    arena = Diagram(len(order), _NODE_LIMIT)
    shared = []
    tables = []
    for role, scope in roles.items():
        factor, table = alphabet_factor(arena, geo, role, fixed, scope, position)
        shared.append(factor)
        tables.append(table)
    for req, scope in zip(checks, navigation_scopes, strict=True):
        shared.append(
            Factor(
                frozenset(position[a] for a in scope),
                _compile_check(arena, req, position, fixed),
            )
        )
    compiled = {
        word: {
            answer: {
                ops: _compile_check(arena, req, position, fixed)
                for ops, req in contacts.items()
            }
            for answer, contacts in answers.items()
        }
        for word, answers in patterns.items()
    }
    return Prepared(
        geo,
        arena.snapshot(),
        fixed,
        order,
        position,
        physical,
        len(order) - len(output_order),
        tuple(shared),
        tuple(tables),
        {
            word: SelectorWord(frozenset(position[a] for a in scope), compiled[word])
            for word, scope in targets.items()
        },
    )


def contact_relation(
    arena: Diagram, prepared: Prepared, word: int, contacts: dict[str, int]
) -> int:
    """Combine unrestricted contacts with the selected side of the joint guard."""
    term = contacts[_ACTIVE]
    guard = _PAIR_GUARDS.get(word)
    if guard is not None:
        restricted, branch_bit = guard
        branch = arena.literal(prepared.position[_PAIR_BRANCH], branch_bit)
        term = arena.combine(
            arena.combine(term, branch),
            contacts[restricted],
            union=True,
        )
    return term


def _requested_relation(
    arena: Diagram,
    prepared: Prepared,
    word: int,
    requested: SelectorBits,
    phase_block: int,
) -> int:
    root = 0
    for answer, contacts in prepared.selectors[word].answers.items():
        phases = sum(
            1 << phase
            for phase in PHASES
            if phase_block >> phase & 1
            and (answer ^ phase) & requested.mask == requested.value
        )
        if not phases:
            continue
        term = contact_relation(arena, prepared, word, contacts)
        root = arena.combine(root, arena.combine(term, phases), union=True)
    return root


def emit(prepared: Prepared, assignment: int) -> bytes:
    """Lift projected colors and materialize the native lookup frame."""
    return render_lookup(
        prepared.geo,
        prepared.alphabet_tables,
        prepared.fixed,
        prepared.order,
        assignment,
    )


def unpack_request(request: tuple[int, ...]) -> SelectorRequest:
    """Pack each word's logical answers into their physical slots."""
    return {
        word: SelectorBits(
            sum(1 << slot for slot, _ in entries),
            sum((answer >> bit & 1) << slot for slot, bit in entries),
        )
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
                    selector.scope,
                    _requested_relation(arena, prepared, word, requested[word], block),
                )
                for word, selector in prepared.selectors.items()
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
