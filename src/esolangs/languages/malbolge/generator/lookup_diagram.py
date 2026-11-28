"""Finite Boolean relations tagged with compatible printer polarities."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from functools import cache
from typing import NamedTuple

PHASES = range(7)
ALL_PHASES = sum(1 << phase for phase in PHASES)
_TERMINALS = ALL_PHASES + 1
type _Node = tuple[int, int, int]


class Checkpoint(NamedTuple):
    """Reusable common factors and their interned nodes."""

    nodes: tuple[_Node, ...]
    unique: dict[_Node, int]


class Diagram:
    """Reduced ordered decision diagrams with seven-bit terminal values."""

    def __init__(self, width: int, limit: int) -> None:
        """Allocate terminals before reserving room for decision nodes."""
        self._limit = limit
        self._nodes: list[_Node] = [(width, i, i) for i in range(_TERMINALS)]
        self._unique: dict[_Node, int] = {}
        self._joined: dict[tuple[int, int, bool], int] = {}
        self._projected: dict[tuple[int, int], int] = {}

    @property
    def size(self) -> int:
        """Return the number of allocated terminals and decisions."""
        return len(self._nodes)

    def node(self, variable: int, low: int, high: int) -> int:
        """Intern the reduced node and return its arena ID."""
        if low == high:
            return low
        key = (variable, low, high)
        found = self._unique.get(key)
        if found is not None:
            return found
        found = len(self._nodes)
        if found == self._limit:
            raise OverflowError("lookup relation exceeds its decision-diagram bound")
        self._nodes.append(key)
        self._unique[key] = found
        return found

    def literal(self, variable: int, bit: int) -> int:
        """Require the named variable to equal its requested bit."""
        return self.node(variable, (1 - bit) * ALL_PHASES, bit * ALL_PHASES)

    def combine(self, left: int, right: int, *, union: bool = False) -> int:
        """Intersect or union the phase masks pointwise."""
        if left == right:
            return left
        if left > right:
            left, right = right, left
        if right < _TERMINALS:
            return left | right if union else left & right
        if left == 0:
            return right if union else 0
        if left == ALL_PHASES:
            return ALL_PHASES if union else right
        key = left, right, union
        result = self._joined.get(key)
        if result is not None:
            return result
        left_var, left_low, left_high = self._nodes[left]
        right_var, right_low, right_high = self._nodes[right]
        if left_var < right_var:
            right_low = right_high = right
        elif right_var < left_var:
            left_low = left_high = left
        result = self.node(
            min(left_var, right_var),
            self.combine(left_low, right_low, union=union),
            self.combine(left_high, right_high, union=union),
        )
        self._joined[key] = result
        return result

    def exists(self, entry: int, variable: int) -> int:
        """Eliminate one variable by unioning its two cofactors."""
        if entry < _TERMINALS:
            return entry
        root, low, high = self._nodes[entry]
        if root > variable:
            return entry
        key = entry, variable
        result = self._projected.get(key)
        if result is not None:
            return result
        if root == variable:
            result = self.combine(low, high, union=True)
        else:
            result = self.node(
                root, self.exists(low, variable), self.exists(high, variable)
            )
        self._projected[key] = result
        return result

    def compile_bits(self, variables: Sequence[int], allowed: int) -> int:
        """Compile a Boolean bitset whose axes are in reverse decision order."""

        @cache
        def visit(depth: int, bits: int) -> int:
            if not bits:
                return 0
            if depth < 0:
                return ALL_PHASES
            stride = 1 << depth
            lower = (1 << stride) - 1
            if bits == lower | (lower << stride):
                return ALL_PHASES
            return self.node(
                variables[depth],
                visit(depth - 1, bits & lower),
                visit(depth - 1, bits >> stride),
            )

        return visit(len(variables) - 1, allowed)

    def evaluate(self, entry: int, assignment: int) -> int:
        """Read the compatible phase mask for a fixed assignment."""
        while entry >= _TERMINALS:
            variable, low, high = self._nodes[entry]
            entry = high if assignment >> variable & 1 else low
        return entry

    def clear_memo(self) -> None:
        """Clear operation caches after an elimination bucket."""
        self._joined.clear()
        self._projected.clear()

    def snapshot(self) -> Checkpoint:
        """Capture shared prefix factors before specializing a request."""
        return Checkpoint(tuple(self._nodes), self._unique.copy())

    def restore(self, checkpoint: Checkpoint) -> None:
        """Restore shared factors and remove request-specific nodes."""
        self.clear_memo()
        self._nodes = list(checkpoint.nodes)
        self._unique = checkpoint.unique.copy()

    def compact(self, roots: Iterable[int]) -> dict[int, int]:
        """Retain the diagrams needed by the remaining factors and backsolve."""
        self.clear_memo()
        old = self._nodes
        self._nodes = old[:_TERMINALS]
        self._unique.clear()
        remap = {i: i for i in range(_TERMINALS)}

        def restore(entry: int) -> int:
            if entry not in remap:
                var, low, high = old[entry]
                remap[entry] = self.node(var, restore(low), restore(high))
            return remap[entry]

        for root in roots:
            restore(root)
        return remap

    def cofactor(
        self, entry: int, colors: int, assignment: int, target: Diagram
    ) -> int:
        """Copy a diagram after fixing every axis from colors onward."""
        copied: dict[int, int] = {}

        def transfer(root: int) -> int:
            if root < _TERMINALS:
                return root
            if root not in copied:
                variable, low, high = self._nodes[root]
                if variable >= colors:
                    result = self.evaluate(root, assignment)
                else:
                    result = target.node(variable, transfer(low), transfer(high))
                copied[root] = result
            return copied[root]

        return transfer(entry)

    def color_nodes(self, entry: int, colors: int) -> int:
        """Count the source nodes that could survive any output cofactor."""
        pending = [entry]
        seen: set[int] = set()
        while pending:
            root = pending.pop()
            if root < _TERMINALS or root in seen:
                continue
            variable, low, high = self._nodes[root]
            if variable < colors:
                seen.add(root)
                pending.extend((low, high))
        return len(seen)

    def truth_mask(self, entry: int, width: int) -> int:
        """Expand a Boolean diagram on the final width axes into a bitset."""
        start = self._nodes[0][0] - width

        @cache
        def visit(root: int, remaining: int) -> int:
            if root < _TERMINALS:
                return (1 << (1 << remaining)) - 1 if root else 0
            variable, low, high = self._nodes[root]
            bit = width - 1 - (variable - start)
            assert 0 <= bit < remaining
            result = visit(low, bit) | (visit(high, bit) << (1 << bit))
            if result and bit + 1 < remaining:
                result *= ((1 << (1 << remaining)) - 1) // ((1 << (1 << (bit + 1))) - 1)
            return result

        return visit(entry, width)
