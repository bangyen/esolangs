"""The one folded decision-tree walk behind SStack's three tree forms.

The plain tree, the label-deferred tree and the binary bank's prefix all
emit the same skeleton: a deferred node where a form shares a residual, a
constant leaf that reads its remaining inputs and prints, a ``;d;`` step
over a level whose halves agree, or a branch whose one arm is emitted
before its zero arm.  What genuinely differs is how each form prices a
node and what its deferred and leaf nodes emit, so those differences
arrive as hooks and this module owns the recursion and the skeleton text.
A constant span is exactly a subtree id below 2, so the leaf test needs
no separate span scan.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

type _Emit = Callable[[str], None]
type _Hit[C] = Callable[[int, int, int, int, Any], C | None]
type _Leaf[C] = Callable[[int, int, int, int, Any], C]


@dataclass(frozen=True, slots=True)
class _Hooks[C]:
    """One form's pricing: deferred hit, leaf, and the two cost wrappers.

    Both node hooks receive ``(depth, key, lo, remaining, context)``, where
    ``key`` is the node's subtree id and ``context`` is whatever the caller
    threads through the walk (the plain tree's shared span, else ``None``).
    A hit returns the node's cost, or ``None`` when the node is not
    deferred; the leaf hook emits the leaf's text and returns its cost.
    """

    hit: _Hit[C]
    leaf: _Leaf[C]
    skipped: Callable[[C], C]
    branched: Callable[[C, C], C]
    leaf_at: Callable[[int, int], bool] = field(default=lambda _depth, key: key < 2)


class _TreeWalk[C]:
    """Emit the folded tree over ``ids``, pricing nodes through ``hooks``."""

    def __init__(self, ids: list[list[int]], emit: _Emit, hooks: _Hooks[C]) -> None:
        self._ids = ids
        self._emit = emit
        self._hooks = hooks
        self._n = len(ids) - 1

    def walk(self, remaining: int, lo: int, context: Any = None) -> C:
        """Walk the span of ``remaining`` inputs starting at row ``lo``."""
        depth = self._n - remaining
        key = self._ids[depth][lo >> remaining]
        hit = self._hooks.hit(depth, key, lo, remaining, context)
        if hit is not None:
            return hit
        if self._hooks.leaf_at(depth, key):
            return self._hooks.leaf(depth, key, lo, remaining, context)
        mid = lo + (1 << (remaining - 1))
        below = self._ids[depth + 1]
        if below[lo >> (remaining - 1)] == below[mid >> (remaining - 1)]:
            self._emit(";d;")
            return self._hooks.skipped(self.walk(remaining - 1, lo, context))
        self._emit(";a;[a\\b/~a~")
        one = self.walk(remaining - 1, mid, context)
        self._emit("][a\\c/~a~")
        zero = self.walk(remaining - 1, lo, context)
        self._emit("]")
        return self._hooks.branched(one, zero)
