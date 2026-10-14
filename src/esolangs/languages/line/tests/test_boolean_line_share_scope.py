"""Ancestor-return scope and area admission for forward residual joins."""

from __future__ import annotations

import random

import pytest

import esolangs
from esolangs.generation.helpers import (
    _residual_ids,
    _validate_truth_table,
    permute_truth_table,
)
from esolangs.languages.line.generator.render import _has_goto
from esolangs.languages.line.generator.shared import shared_tree
from esolangs.languages.line.tests.test_boolean_line_projection import _execute
from tests.support.witness_tables import parity


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
    """Forward joins extend the ancestor mechanism's structured scope."""

    def test_parity_and_majority_have_no_reachable_fork(self) -> None:
        """No fork at all can re-descend to the nodes these tables repeat."""
        for build in (parity, _majority):
            for n in range(5, 9):
                table = build(n)
                assert _reachable_forks(table) == 0, (build.__name__, n)
                assert shared_tree(table, multiple=True) is None, (build.__name__, n)

    def test_forward_joins_admit_parity_beyond_ancestor_return_scope(self) -> None:
        """Streaming stems admit parity at n=5 and majority at n=6."""
        for build in (parity, _majority):
            for n in range(5, 9):
                payload = esolangs.generate("Line", build(n))._payload  # noqa: SLF001
                assert _has_goto(payload) == (n >= (5 if build is parity else 6)), (
                    build.__name__,
                    n,
                )

    @pytest.mark.medium
    @pytest.mark.parametrize("start", [0, 50, 100, 150])
    @pytest.mark.parametrize(
        ("n", "shared_counts", "fork_counts"),
        [
            (5, (0, 0, 0, 0), (74, 74, 72, 95)),
            pytest.param(6, (2, 1, 1, 0), (126, 125, 127, 137), marks=pytest.mark.slow),
            pytest.param(7, (1, 0, 1, 1), (231, 218, 194, 211), marks=pytest.mark.slow),
            (8, (0, 0, 0, 0), (363, 348, 335, 315)),
        ],
    )
    def test_random_tables_rarely_admit_shared_layouts(
        self,
        n: int,
        start: int,
        shared_counts: tuple[int, ...],
        fork_counts: tuple[int, ...],
    ) -> None:
        """7 of 800 seeded tables share; execute every admitted input row."""
        tables = _sample(n, 200, seed=11 + n)[start : start + 50]
        gotos = 0
        for table in tables:
            generated = esolangs.generate("Line", table)
            if _has_goto(generated._payload):  # noqa: SLF001
                _execute(table, generated, range(1 << n))
                gotos += 1
        assert gotos == shared_counts[start // 50]
        assert (
            sum(_reachable_forks(table) for table in tables) == fork_counts[start // 50]
        )
