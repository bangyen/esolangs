"""Disjoint join-row packing and native controls for the reduced channel."""

import importlib
import random
from itertools import combinations

import pytest

from esolangs.languages.line.generator.forward import (
    _join_lanes,
)
from esolangs.languages.line.generator.forward import (
    streaming_canvas as forward_canvas,
)
from esolangs.languages.line.tests.test_boolean_line_forward import _check


def test_disjoint_spans_reuse_rows_with_a_three_unit_gap() -> None:
    a, b, c = (0, 0, 0), (0, 1, 0), (0, 2, 0)
    lanes, count = _join_lanes([(a, 0, 8), (b, 11, 20), (c, 10, 0)])
    assert count == 2
    assert lanes[a] == lanes[b]
    assert lanes[c] != lanes[a]
    assert _join_lanes([]) == ({}, 0)


def test_lane_count_matches_padded_interval_concurrency() -> None:
    rng = random.Random(11)
    for _ in range(100):
        spans = [
            ((i, 0, 0), rng.randrange(-20, 40), rng.randrange(-20, 40))
            for i in range(20)
        ]
        lanes, count = _join_lanes(spans)
        expected = max(
            sum(min(a, b) - 1 <= x <= max(a, b) + 1 for _, a, b in spans)
            for x in range(-21, 41)
        )
        assert count == expected
        assert set(lanes) == {edge for edge, _, _ in spans}
        for (a, x0, x1), (b, y0, y1) in combinations(spans, 2):
            if lanes[a] == lanes[b]:
                assert max(x0, x1) + 2 < min(y0, y1) or max(y0, y1) + 2 < min(x0, x1)


@pytest.mark.medium
@pytest.mark.parametrize("n", [4, 5, 6])
def test_seeded_joined_graphs_execute_every_row(n, tmp_path) -> None:
    rng = random.Random(37 + n)
    admitted = 0
    for _ in range(8):
        table = "".join(rng.choice("01") for _ in range(1 << n))
        if forward_canvas(table, 10**9) is not None:
            _check(table, tmp_path)
            admitted += 1
    assert admitted > 0


@pytest.mark.slow
def test_majority22_packing_beats_unique_rows_with_native_contracts(
    tmp_path, monkeypatch
) -> None:
    n = 22
    table = "".join(str(int(row.bit_count() > n // 2)) for row in range(1 << n))
    rows = sorted(
        {
            0,
            len(table) - 1,
            (1 << 11) - 1,
            (1 << 12) - 1,
            ((1 << 11) - 1) << 11,
            ((1 << 12) - 1) << 10,
            *range(0, len(table), len(table) // 32),
        }
    )
    module = importlib.import_module("esolangs.languages.line.generator.forward")
    with monkeypatch.context() as baseline:
        baseline.setattr(
            module,
            "_join_lanes",
            lambda spans: (
                {edge: i for i, (edge, _, _) in enumerate(spans)},
                len(spans),
            ),
        )
        old_area, old_commands = _check(table, tmp_path, rows)
    area, commands = _check(table, tmp_path, rows)
    assert (old_area, area) == (42_112_000, 25_568_000)
    assert area < 0.9 * old_area
    assert commands == old_commands == 58


@pytest.mark.medium
def test_scaled_disjoint_join_rows_execute(tmp_path) -> None:
    table = "".join(str(int(row.bit_count() > 4)) for row in range(256))
    area, _ = _check(table, tmp_path, scale=2)
    assert area == 3_952_000
