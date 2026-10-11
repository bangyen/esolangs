"""Boolfuck's repeated-node upside is below the sharing gate.

``docs/limitations.md`` records Boolfuck's sharing exemption with the screen's
figure; this pins it so the number stays reproducible rather than prose.
"""

from __future__ import annotations

from esolangs.tools.boolfuck import boolfuck
from tests.support.witness_tables import parity
from tests.tools.sample_tables import five_input_sample


def _repeated_nodes(table: str) -> int:
    """Non-constant subtables less the distinct ones, summed per level."""
    repeated = distinct = 0
    width = len(table)
    while width > 1:
        level = [table[i : i + width] for i in range(0, len(table), width)]
        live = [sub for sub in level if len(set(sub)) > 1]
        repeated += len(live)
        distinct += len(set(live))
        width //= 2
    return repeated - distinct


def test_repeated_node_upside_is_below_the_sharing_gate() -> None:
    """The screen's n=5 upside is 2.3% of emitted size, so no share pays."""
    cost = (len(boolfuck(parity(5))) - len(boolfuck(parity(3)))) / (31 - 7)
    sample = five_input_sample()
    saved = sum(_repeated_nodes(table) for table in sample) * cost
    total = sum(len(boolfuck(table)) for table in sample)
    assert (round(saved), total) == (1992, 85_766)
    assert 100 * saved / total < 5  # the sharing gate is 10%
