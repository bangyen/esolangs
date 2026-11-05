"""Ordered decision layers; each emitter owns its input-consumption policy."""

from itertools import pairwise
from typing import NamedTuple

from esolangs.generation.helpers import subtree_ids


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
