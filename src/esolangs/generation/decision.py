"""Ordered decision layers and reduced Shannon diagrams."""

from collections.abc import Callable, Mapping
from itertools import pairwise
from types import MappingProxyType
from typing import NamedTuple

from esolangs.generation.helpers import _validate_truth_table, subtree_ids


def residual_count_bound(n: int, *, include_constants: bool = True) -> int:
    """Sum distinct subtable caps over internal levels, before reduction."""
    if n <= 1:
        return n

    # A level with h inputs left saturates when it has at least 2^(2^h)
    # positions, equivalently h+2^h <= n. Excluding the two constant
    # subtables moves only the h=1, n=2 tie, where the count is unchanged.
    saturated = n.bit_length() - 1
    saturated -= n < saturated + (1 << saturated)

    # Shallower levels use their position caps. Only build the small
    # towers at the saturated end, where their exponents are at most n.
    prefix = (1 << (n - saturated)) - 1
    tail = sum(1 << (1 << h) for h in range(1, saturated + 1))
    return prefix + tail - (0 if include_constants else 2 * saturated)


class DecisionLayers(NamedTuple):
    """Immutable child maps in physical input order, including constant layers."""

    root: int
    children: tuple[Mapping[int, tuple[int, int]], ...]


_FOLD_CHUNK = 256


def decision_layers(truth_table: str) -> DecisionLayers:
    """Index subtable children in O(T), ordered by leftmost occurrence.

    Constants retain their layers: deciding which reads to omit or drain
    belongs to the emitter. Only the first copy of each parent is expanded.
    Results are read-only; emitters own labels, reads and layout state.
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
        layers.append(MappingProxyType(layer))
        frontier = following
    return DecisionLayers(ids[0][0], tuple(layers))


def fold_subtables[V](
    truth_table: str,
    terminals: Mapping[str, V],
    branch: Callable[[V, V], V],
) -> V:
    """Fold in left-first order with linear analysis and emitter-owned branches."""
    _validate_truth_table(truth_table)
    if "0" not in terminals or "1" not in terminals:
        raise ValueError("subtable folding requires both Boolean leaves")
    text_memo = dict(terminals)
    if len(truth_table) <= _FOLD_CHUNK or truth_table in text_memo:
        return _fold_text(truth_table, text_memo, branch)
    return _fold_indexed(truth_table, text_memo, branch)


def _fold_text[V](table: str, memo: dict[str, V], branch: Callable[[V, V], V]) -> V:
    if table not in memo:
        half = len(table) // 2
        memo[table] = branch(
            _fold_text(table[:half], memo, branch),
            _fold_text(table[half:], memo, branch),
        )
    return memo[table]


def _fold_indexed[V](
    table: str, text_memo: dict[str, V], branch: Callable[[V, V], V]
) -> V:
    """Intern large spans, leaving bounded-size chunks to the text fold."""
    span = _FOLD_CHUNK
    chunks: dict[str, int] = {}
    level = []
    for start in range(0, len(table), span):
        chunk = table[start : start + span]
        level.append(chunks.setdefault(chunk, len(chunks)))
    base = tuple(chunks)
    pairs: dict[tuple[int, int], int] = {}
    children: list[tuple[int, int]] = []
    while len(level) > 1:
        halves = iter(level)
        level = []
        for pair in zip(halves, halves, strict=True):
            node = pairs.get(pair)
            if node is None:
                node = pairs[pair] = len(base) + len(children)
                children.append(pair)
            level.append(node)
    memo: dict[int, V] = {}
    for text, value in text_memo.items():
        size = len(text)
        if size <= span or size & (size - 1):
            continue
        try:
            parts = [
                chunks[text[start : start + span]]
                for start in range(0, len(text), span)
            ]
            while len(parts) > 1:
                halves = iter(parts)
                parts = [pairs[pair] for pair in zip(halves, halves, strict=True)]
        except KeyError:
            continue
        memo[parts[0]] = value
    return _fold_node(level[0], base, children, memo, text_memo, branch)


def _fold_node[V](
    node: int,
    base: tuple[str, ...],
    children: list[tuple[int, int]],
    memo: dict[int, V],
    text_memo: dict[str, V],
    branch: Callable[[V, V], V],
) -> V:
    if node < len(base):
        return _fold_text(base[node], text_memo, branch)
    if node not in memo:
        zero, one = children[node - len(base)]
        memo[node] = branch(
            _fold_node(zero, base, children, memo, text_memo, branch),
            _fold_node(one, base, children, memo, text_memo, branch),
        )
    return memo[node]


class DecisionNode(NamedTuple):
    """A diagram node: a selector level and the ids of its two halves."""

    level: int
    zero: int
    one: int


def reduced_diagram(truth_table: str, n: int) -> tuple[tuple[DecisionNode, ...], int]:
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
    return tuple(nodes), ids[0]


type DecisionKey = tuple[int, int]
type DecisionRef = tuple[DecisionKey, bool]


class ComplementedDiagram(NamedTuple):
    """Level/subtree keys and references carrying an output-complement bit."""

    nodes: Mapping[DecisionKey, tuple[int, DecisionRef, DecisionRef]]
    root: DecisionRef


def complement_ref(half: DecisionRef) -> DecisionRef:
    """Complement a reference, normalizing constant leaves to unflipped 0/1."""
    (level, node), negated = half
    return ((level, node ^ negated ^ 1), False) if node < 2 else (half[0], not negated)


def complemented_diagram(truth_table: str) -> ComplementedDiagram:
    """Fold equal/complementary halves in O(T), retaining first-seen level keys.

    Constant keys retain their level. Selector spelling, input order and
    whether to materialize a complemented edge belong to the emitter.
    """
    ids = subtree_ids(truth_table)
    n = len(ids) - 1
    nodes: dict[DecisionKey, tuple[int, DecisionRef, DecisionRef]] = {}
    refs: dict[DecisionKey, DecisionRef] = {}
    made: dict[tuple[int, DecisionRef, DecisionRef], DecisionKey] = {}

    def resolve(key: DecisionKey) -> DecisionRef:
        return (key, False) if key[1] < 2 else refs[key]

    for depth in range(n - 1, -1, -1):
        for place, node in enumerate(ids[depth]):
            key = (depth, node)
            if node < 2 or key in refs:
                continue
            zero = resolve((depth + 1, ids[depth + 1][2 * place]))
            one = resolve((depth + 1, ids[depth + 1][2 * place + 1]))
            if zero == one:
                refs[key] = zero
            elif (
                twin := made.get((depth, complement_ref(zero), complement_ref(one)))
            ) is not None:
                refs[key] = (twin, True)
            else:
                refs[key] = (key, False)
                made[depth, zero, one] = key
                nodes[key] = (depth, zero, one)
    return ComplementedDiagram(MappingProxyType(nodes), resolve((0, ids[0][0])))
