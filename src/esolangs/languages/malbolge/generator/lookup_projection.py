"""Project selectors with the right operand fixed to one physical pattern."""

from __future__ import annotations

from collections.abc import Callable
from functools import cache, reduce

from .lookup_diagram import ALL_PHASES, PHASES, Diagram
from .lookup_elimination import Factor, take_bucket
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
from .packed import _RIGHT_OPERAND

_WITNESS_LIMIT = 2_000_000


def project(
    plan: Prepared, capture: Callable[[Diagram, int, int, int], None]
) -> tuple[Diagram, int]:
    """Eliminate colors while reporting the buckets before projection."""
    assert plan.physical is not None
    _, _, axes = selector_axes()
    arena = Diagram(len(plan.order), _NODE_LIMIT)
    arena.restore(plan.checkpoint)
    pending = list(plan.shared)
    for word, selector in plan.selectors.items():
        root = 0
        for pattern, contacts in selector.answers.items():
            term = contact_relation(arena, plan, word, contacts)
            for slot, axis in axes.get(word, {}).items():
                literal = arena.literal(
                    plan.position[_OUTPUT, axis], pattern >> slot & 1
                )
                term = arena.combine(term, literal)
            root = arena.combine(root, term, union=True)
        pending.append(Factor(selector.scope, root))
    for variable in range(plan.color_count):
        bucket = take_bucket(arena, pending, variable)
        if bucket is None:
            continue
        capture(arena, bucket.joint, variable, plan.color_count)
        projected = arena.exists(bucket.joint, variable)
        arena.clear_memo()
        if not projected:
            return arena, 0
        pending.append(Factor(bucket.remaining_scope, projected))
        if arena.size > 150_000:
            mapping = arena.compact(factor.root for factor in pending)
            pending = [Factor(factor.scope, mapping[factor.root]) for factor in pending]
    return arena, reduce(arena.combine, (factor.root for factor in pending), ALL_PHASES)


@cache
def _output_phase_flips() -> tuple[int, ...]:
    """Pack each phase's flips relative to the start of the output suffix."""
    width, _, axes = selector_axes()
    return tuple(
        sum(
            (phase >> slot & 1) << (width - 1 - axis)
            for slots in axes.values()
            for slot, axis in slots.items()
        )
        for phase in PHASES
    )


def select_bounded(requested: SelectorRequest) -> tuple[bytes, int]:
    """Recover a layout by retaining only the requested output cofactors."""
    width, pin, axes = selector_axes()
    right = requested[_RIGHT_OPERAND].value
    logical = sum((right >> slot & 1) << rank for rank, slot in enumerate(pin))
    # The prepared output suffix places the highest axis first.
    output = sum(
        (requested[word].value >> slot & 1) << (width - 1 - axis)
        for word, slots in axes.items()
        for slot, axis in slots.items()
    )
    for phase, flip in zip(PHASES, _output_phase_flips(), strict=True):
        plan = prepare(logical ^ phase)
        lookup = _recover(plan, (output ^ flip) << plan.color_count)
        if lookup is not None:
            return lookup, phase
    raise AssertionError("selector coverage is incomplete")


def _recover(plan: Prepared, output: int) -> bytes | None:
    """Copy output cofactors into their own arena before each bucket is lost."""
    target = Diagram(plan.color_count, _WITNESS_LIMIT)
    history: list[tuple[int, int]] = []

    def retain(arena: Diagram, root: int, variable: int, colors: int) -> None:
        history.append((variable, arena.cofactor(root, colors, output, target)))

    arena, root = project(plan, retain)
    if not arena.evaluate(root, output):
        return None
    assignment = 0
    for variable, bucket in reversed(history):
        if not target.evaluate(bucket, assignment):
            assignment |= 1 << variable
        assert target.evaluate(bucket, assignment)
    return emit(plan, assignment)
