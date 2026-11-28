"""Project selectors with the right operand fixed to one physical pattern."""

from __future__ import annotations

from collections.abc import Callable
from functools import reduce

from .lookup_diagram import ALL_PHASES, Diagram
from .lookup_elimination import Factor
from .lookup_request import (
    _NODE_LIMIT,
    _OUTPUT,
    Prepared,
    SelectorRequest,
    contact_relation,
    emit,
    prepare,
    selector_axes,
)
from .packed import _RIGHT_OPERAND, _selector_groups

_WITNESS_LIMIT = 2_000_000


def project(
    physical: int, capture: Callable[[Diagram, int, int, int], None]
) -> tuple[Diagram, int]:
    """Eliminate colors while reporting the buckets before projection."""
    plan = prepare(physical)
    width, _, axes = selector_axes(plan.groups)
    colors = len(plan.order) - width
    arena = Diagram(len(plan.order), _NODE_LIMIT)
    arena.restore(plan.checkpoint)
    pending = list(plan.shared)
    for word, scope in plan.targets.items():
        root = 0
        for pattern in (physical,) if word == _RIGHT_OPERAND else range(8):
            term = contact_relation(arena, plan, word, pattern)
            for slot, axis in axes.get(word, {}).items():
                literal = arena.literal(
                    plan.position[_OUTPUT, axis], pattern >> slot & 1
                )
                term = arena.combine(term, literal)
            root = arena.combine(root, term, union=True)
        pending.append(Factor(scope, root))
    for variable in range(colors):
        group = [factor for factor in pending if variable in factor.scope]
        if not group:
            continue
        pending = [factor for factor in pending if variable not in factor.scope]
        joint = reduce(
            arena.combine,
            (
                factor.root
                for factor in sorted(group, key=lambda factor: len(factor.scope))
            ),
            ALL_PHASES,
        )
        capture(arena, joint, variable, colors)
        projected = arena.exists(joint, variable)
        arena.clear_memo()
        if not projected:
            return arena, 0
        involved = frozenset().union(*(factor.scope for factor in group))
        pending.append(Factor(involved - {variable}, projected))
        if arena.size > 150_000:
            mapping = arena.compact(factor.root for factor in pending)
            pending = [Factor(factor.scope, mapping[factor.root]) for factor in pending]
    return arena, reduce(arena.combine, (factor.root for factor in pending), ALL_PHASES)


def select_bounded(requested: SelectorRequest) -> tuple[bytes, int]:
    """Recover a layout by retaining only the requested output cofactors."""
    width, pin, axes = selector_axes(_selector_groups())
    right = requested[_RIGHT_OPERAND]
    logical = sum(right[slot] << rank for rank, slot in enumerate(pin))
    for phase in range(7):
        physical = logical ^ phase
        plan = prepare(physical)
        colors = len(plan.order) - width
        output = 0
        for word, slots in axes.items():
            for slot, axis in slots.items():
                bit = requested[word][slot] ^ (phase >> slot & 1)
                output |= bit << plan.position[_OUTPUT, axis]
        lookup = _recover(plan, physical, output, colors)
        if lookup is not None:
            return lookup, phase
    raise AssertionError("selector coverage is incomplete")


def _recover(plan: Prepared, physical: int, output: int, colors: int) -> bytes | None:
    """Copy output cofactors into their own arena before each bucket is lost."""
    target = Diagram(colors, _WITNESS_LIMIT)
    history: list[tuple[int, int]] = []

    def retain(arena: Diagram, root: int, variable: int, colors: int) -> None:
        history.append((variable, arena.cofactor(root, colors, output, target)))

    arena, root = project(physical, retain)
    if not arena.evaluate(root, output):
        return None
    assignment = 0
    for variable, bucket in reversed(history):
        if not target.evaluate(bucket, assignment):
            assignment |= 1 << variable
        assert target.evaluate(bucket, assignment)
    return emit(plan, assignment)
