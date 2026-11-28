"""Eliminate lookup color variables and reconstruct a satisfying assignment."""

from __future__ import annotations

from functools import reduce
from itertools import combinations
from typing import TYPE_CHECKING, NamedTuple

from .lookup_diagram import ALL_PHASES, Diagram

if TYPE_CHECKING:
    from collections.abc import Iterable


class Factor(NamedTuple):
    """A diagram and a conservative scope of its color variables."""

    scope: frozenset[int]
    root: int


class Bucket(NamedTuple):
    """The ordered roots and conjunction of factors that touch one variable."""

    roots: tuple[int, ...]
    joint: int
    remaining_scope: frozenset[int]


class Witness(NamedTuple):
    """Compatible printer phases and the buckets used to recover colors."""

    phases: int
    history: list[tuple[int, tuple[int, ...]]]


def min_fill(
    scopes: Iterable[frozenset[int]], deferred: frozenset[int] = frozenset()
) -> tuple[int, ...]:
    """Order color variables by the number of new factor edges they create."""
    graph: dict[int, set[int]] = {}
    for scope in scopes:
        for vertex in scope:
            graph.setdefault(vertex, set()).update(scope - {vertex})

    def cost(vertex: int) -> tuple[bool, int, int, int]:
        neighbors = graph[vertex]
        added = sum(b not in graph[a] for a, b in combinations(sorted(neighbors), 2))
        return vertex in deferred, added, len(neighbors), vertex

    result = []
    while graph:
        best = min(graph, key=cost)
        result.append(best)
        neighbors = graph.pop(best)
        for neighbor in neighbors:
            graph[neighbor].discard(best)
            graph[neighbor].update(neighbors - {neighbor})
    return tuple(result)


def take_bucket(arena: Diagram, pending: list[Factor], variable: int) -> Bucket | None:
    """Remove the factors that touch a variable and combine them in scope order."""
    work = [factor for factor in pending if variable in factor.scope]
    if not work:
        return None
    pending[:] = [factor for factor in pending if variable not in factor.scope]
    roots = tuple(factor.root for factor in sorted(work, key=lambda f: len(f.scope)))
    joint = reduce(arena.combine, roots, ALL_PHASES)
    scope = frozenset().union(*(factor.scope for factor in work))
    return Bucket(roots, joint, scope - {variable})


def eliminate(
    arena: Diagram, factors: Iterable[Factor], order: Iterable[int]
) -> Witness:
    """Project a bucket after each variable to avoid a global conjunction."""
    pending = list(factors)
    history: list[tuple[int, tuple[int, ...]]] = []
    for variable in order:
        bucket = take_bucket(arena, pending, variable)
        if bucket is None:
            continue
        projected = arena.exists(bucket.joint, variable)
        arena.clear_memo()
        if not projected:
            return Witness(0, [])
        pending.append(Factor(bucket.remaining_scope, projected))
        history.append((variable, bucket.roots))
        if arena.size > 160_000 and len(history) % 3 == 0:
            remap = arena.compact(
                [*(r for _, r in pending), *(r for _, rs in history for r in rs)]
            )
            pending = [Factor(scope, remap[root]) for scope, root in pending]
            history = [(v, tuple(remap[root] for root in rs)) for v, rs in history]
    assert all(not factor.scope for factor in pending)
    phases = reduce(arena.combine, (factor.root for factor in pending), ALL_PHASES)
    assert 0 <= phases <= ALL_PHASES
    return Witness(phases, history)


def reconstruct(arena: Diagram, witness: Witness, phase: int) -> int:
    """Set each eliminated variable to the low valid branch in reverse order."""
    assert witness.phases >> phase & 1
    assignment = 0
    for variable, roots in reversed(witness.history):
        if not all(arena.evaluate(root, assignment) >> phase & 1 for root in roots):
            assignment |= 1 << variable
        assert all(arena.evaluate(root, assignment) >> phase & 1 for root in roots)
    return assignment
