"""Area admission for forward residual joins."""

from __future__ import annotations

import random

import pytest

import esolangs
from esolangs.languages.line.generator.layout import _has_goto
from esolangs.languages.line.tests.test_boolean_line_projection import _execute
from tests.support.witness_tables import parity


def _majority(n: int) -> str:
    """The ``n``-input majority table."""
    return "".join("1" if row.bit_count() > n // 2 else "0" for row in range(1 << n))


def _sample(n: int, count: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    return ["".join(rng.choice("01") for _ in range(1 << n)) for _ in range(count)]


class TestLineReturnScope:
    """Forward joins admit the structured tables."""

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
        ("n", "shared_counts"),
        [
            (5, (0, 0, 0, 0)),
            pytest.param(6, (2, 1, 1, 0), marks=pytest.mark.slow),
            pytest.param(7, (1, 0, 1, 1), marks=pytest.mark.slow),
            (8, (0, 0, 0, 0)),
        ],
    )
    def test_random_tables_rarely_admit_shared_layouts(
        self,
        n: int,
        start: int,
        shared_counts: tuple[int, ...],
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
