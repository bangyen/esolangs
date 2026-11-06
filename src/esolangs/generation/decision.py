"""Ordered decision layers and reduced Shannon diagrams."""

from collections.abc import Callable, Mapping
from itertools import pairwise
from typing import NamedTuple

from esolangs.generation.helpers import _validate_truth_table, subtree_ids


class DecisionLayers(NamedTuple):
    """Root id and ordered child maps, retaining constants at each input layer."""

    root: int
    children: list[dict[int, tuple[int, int]]]


def decision_layers(truth_table: str) -> DecisionLayers:
    """Index subtable children in O(T), ordered by leftmost occurrence.

    Constants retain their layers: deciding which reads to omit or drain
    belongs to the emitter. Only the first copy of each parent is expanded.
    """
    ids = subtree_ids(truth_table)
    layers = []
    frontier = [0]
    for row, under in pairwise(ids):
        layer: dict[int, tuple[int, int]] = {}
        following: list[int] = []
        for block in frontier:
            node = row[block]
            if node not in layer:
                layer[node] = (under[2 * block], under[2 * block + 1])
                following.extend((2 * block, 2 * block + 1))
        layers.append(layer)
        frontier = following
    return DecisionLayers(ids[0][0], layers)


def fold_subtables[V](
    truth_table: str,
    terminals: Mapping[str, V],
    branch: Callable[[V, V], V],
) -> V:
    """Fold distinct subtables once, using emitter-owned terminals and branches."""
    _validate_truth_table(truth_table)
    if "0" not in terminals or "1" not in terminals:
        raise ValueError("subtable folding requires both Boolean leaves")
    return _fold_subtable(truth_table, dict(terminals), branch)


def _fold_subtable[V](table: str, memo: dict[str, V], branch: Callable[[V, V], V]) -> V:
    """Resolve one subtable without retaining a recursive closure after the fold."""
    if table not in memo:
        half = len(table) // 2
        memo[table] = branch(
            _fold_subtable(table[:half], memo, branch),
            _fold_subtable(table[half:], memo, branch),
        )
    return memo[table]


class DecisionNode(NamedTuple):
    """A diagram node: a selector level and the ids of its two halves."""

    level: int
    zero: int
    one: int


def reduced_diagram(truth_table: str, n: int) -> tuple[list[DecisionNode], int]:
    """Return a reduced Shannon DAG and root for a validated n-input table.

    Constants have ids 0/1; other nodes follow their children, level by level
    and left to right. Equal halves collapse; interning costs O(T).
    """
    nodes = [DecisionNode(n, 0, 0), DecisionNode(n, 1, 1)]
    # Plain tuples key the index: a NamedTuple per row pair was most of the
    # build at 21 inputs, and the two hash and compare alike.
    index: dict[tuple[int, int, int], int] = {}
    ids = [int(bit) for bit in truth_table]
    for level in range(n - 1, -1, -1):
        halves, ids = ids, []
        for zero, one in zip(halves[::2], halves[1::2], strict=True):
            if zero == one:
                ids.append(zero)
                continue
            key = (level, zero, one)
            found = index.get(key)
            if found is None:
                found = index[key] = len(nodes)
                nodes.append(DecisionNode(*key))
            ids.append(found)
    return nodes, ids[0]
