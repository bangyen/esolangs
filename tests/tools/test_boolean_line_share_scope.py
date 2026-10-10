"""Line's ancestor returns miss the screen's repeated-subtree upside.

The sharing screen (``scripts/screens/sharing.py``) weights repeated
non-constant subtables at 40.3% of Line's n=5 emitted area.  Line has one
share: an ancestor return that re-descends a *test-free* arm -- a fork whose
one arm is a chain of equal-halves nodes to a residual that recurs in the
other arm at the matching depth.  These controls pin that the mechanism
reaches none of the screen's structured dominance, and that no return
survives into a generated program on random tables even though reachable
fork candidates exist: the residual gap is a layout wall -- same-level
duplicates need bus routing Line's crossing-free strokes forbid -- not a
better pick among one residual's occurrences.
"""

from __future__ import annotations

import random

import pytest

import esolangs
from esolangs.tools.helpers import (
    _residual_ids,
    _validate_truth_table,
    permute_truth_table,
)
from esolangs.tools.line.render import _has_goto
from esolangs.tools.line.shared import shared_tree
from tests.witness_tables import parity


def _majority(n: int) -> str:
    """The ``n``-input majority table."""
    return "".join("1" if row.bit_count() > n // 2 else "0" for row in range(1 << n))


def _sample(n: int, count: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    return ["".join(rng.choice("01") for _ in range(1 << n)) for _ in range(count)]


def _reachable_forks(table: str) -> int:
    """Distinct forks carrying a test-free-arm ancestor return, upper bound.

    Counts any fork, either arm, not only the root's zero chain the generator
    tries: the mechanism's whole reachable set.  ``_residual_ids`` gives the
    canonical residual DAG; a fork's arm is walked while its two halves agree
    (a test-free descent, no cell read), and each level's residual is matched
    against the other arm at the same relative depth.
    """
    n = _validate_truth_table(table)
    order = (1, 0, *range(2, n))
    _, children, constants = _residual_ids(permute_truth_table(table, order), n)

    def members(root: int, depth: int) -> set[int]:
        """Residuals at relative ``depth`` below ``root``."""
        current = {root}
        for _ in range(depth - 1):
            nxt: set[int] = set()
            for r in current:
                if constants[r] is None:
                    nxt.update(children[r])
                else:
                    nxt.add(r)
            current = nxt
        return current

    forks = 0
    for fork, (zero, one) in children.items():
        if constants[fork] is not None:
            continue
        found = False
        for arm, other in ((zero, one), (one, zero)):
            if constants[arm] is not None:
                continue
            r, depth = arm, 1
            while True:
                if r in members(other, depth):
                    found = True
                    break
                if constants[r] is not None or children[r][0] != children[r][1]:
                    break
                r = children[r][0]
                depth += 1
        if found:
            forks += 1
    return forks


class TestLineReturnScope:
    """The screen's structured cases and random tables carry no usable share."""

    def test_parity_and_majority_have_no_reachable_fork(self) -> None:
        """No fork at all can re-descend to the nodes these tables repeat."""
        for build in (parity, _majority):
            for n in range(5, 9):
                table = build(n)
                assert _reachable_forks(table) == 0, (build.__name__, n)
                assert shared_tree(table, multiple=True) is None, (build.__name__, n)

    def test_parity_and_majority_generate_no_return(self) -> None:
        """The shipped generator emits no loop-back for either family."""
        for build in (parity, _majority):
            for n in range(5, 9):
                payload = esolangs.generate("Line", build(n))._payload  # noqa: SLF001
                assert not _has_goto(payload), (build.__name__, n)

    @pytest.mark.medium  # 1.6s: 800 generated graphs
    def test_random_tables_generate_no_return(self) -> None:
        """200 seeded tables per arity n=5..8: no program carries a loop-back.

        Reachable fork candidates are present (the counter sums below), so the
        wall is overhead and layout, not scarcity; the generator still keeps
        the plain tree because every shared build is larger or fails to draw.
        """
        totals = []
        for n in range(5, 9):
            tables = _sample(n, 200, seed=11 + n)
            gotos = sum(
                1
                for table in tables
                if _has_goto(esolangs.generate("Line", table)._payload)  # noqa: SLF001
            )
            assert gotos == 0, n
            totals.append(sum(_reachable_forks(table) for table in tables))
        assert tuple(totals) == (315, 515, 854, 1361)
