"""Native controls for median-parent streamed ordering."""

import pytest

from esolangs.languages.line.generator import line
from esolangs.languages.line.generator.forward import median_streaming_canvas
from esolangs.languages.line.tests import test_boolean_line_forward as controls
from esolangs.languages.line.tests.test_boolean_line_forward import _check
from esolangs.languages.line.tests.test_boolean_line_projection import _execute
from esolangs.languages.line.tests.test_boolean_line_share_scope import _sample
from tests.support.witness_tables import dense, parity


@pytest.fixture
def median_check(monkeypatch):
    monkeypatch.setattr(controls, "forward_canvas", median_streaming_canvas)
    return _check


@pytest.mark.medium
@pytest.mark.parametrize("start", [0, 64, 128, 192])
def test_median_three_input_graphs_execute(start, median_check, tmp_path) -> None:
    admitted = 0
    for value in range(start, start + 64):
        table = f"{value:08b}"
        if median_streaming_canvas(table, 10**9) is not None:
            median_check(table, tmp_path)
            admitted += 1
    assert admitted == {0: 61, 64: 63, 128: 63, 192: 61}[start]


@pytest.mark.medium
@pytest.mark.parametrize(
    "kind", [pytest.param("dense", marks=pytest.mark.slow), "parity", "majority"]
)
def test_median_eight_input_graphs_execute(kind, median_check, tmp_path) -> None:
    table = (
        dense(8)
        if kind == "dense"
        else parity(8)
        if kind == "parity"
        else "".join(str(int(row.bit_count() > 4)) for row in range(256))
    )
    area, commands = median_check(table, tmp_path)
    assert (
        area == {"dense": 36_982_400, "parity": 1_534_400, "majority": 3_982_400}[kind]
    )
    assert commands == {"dense": 23, "parity": 27, "majority": 23}[kind]


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "index", "area", "old"),
    [(6, 4, 6_216_000, 6_403_200), (7, 13, 13_910_400, 14_515_200)],
)
def test_public_median_improvements_execute(
    n, index, area, old, median_check, tmp_path
) -> None:
    table = _sample(n, index + 1, 11 + n)[index]
    measured, _ = median_check(table, tmp_path)
    assert measured == area < old
    generated = line(table)
    assert len(generated.rows) * len(generated.rows[0]) <= area
    _execute(table, generated, range(1 << n))


@pytest.mark.medium
def test_median_scaled_crossings(median_check, tmp_path) -> None:
    median_check(parity(7), tmp_path, scale=2)
