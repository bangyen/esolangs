"""Reduced diagrams retain every truth row without redundant selectors."""

import itertools

import pytest

from esolangs.generation.decision import reduced_diagram


@pytest.mark.parametrize("n", range(4))
def test_reduced_diagram_preserves_every_truth_row(n):
    for bits in itertools.product("01", repeat=1 << n):
        table = "".join(bits)
        nodes, root = reduced_diagram(table, n)
        assert len(nodes) <= len(table) + 1
        assert len(set(nodes[2:])) == len(nodes) - 2
        for key, node in enumerate(nodes[2:], 2):
            assert node.zero != node.one
            assert max(node.zero, node.one) < key
            assert node.level < nodes[node.zero].level
            assert node.level < nodes[node.one].level
        for row, expected in enumerate(table):
            key = root
            while key > 1:
                level, zero, one = nodes[key]
                key = one if row & (1 << (n - 1 - level)) else zero
            assert str(key) == expected
