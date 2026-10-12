"""Native controls for centered streamed columns."""

import pytest

from esolangs.languages.line.generator.forward import centered_streaming_canvas
from esolangs.languages.line.tests import test_boolean_line_forward as controls
from esolangs.languages.line.tests.test_boolean_line_forward import _check
from tests.support.witness_tables import dense, parity


@pytest.fixture
def centered_check(monkeypatch):
    monkeypatch.setattr(controls, "forward_canvas", centered_streaming_canvas)
    return _check


@pytest.mark.medium
@pytest.mark.parametrize("start", [0, 64, 128, 192])
def test_centered_three_input_graphs_execute(start, centered_check, tmp_path):
    admitted = 0
    for value in range(start, start + 64):
        table = f"{value:08b}"
        if centered_streaming_canvas(table, 10**9) is not None:
            centered_check(table, tmp_path)
            admitted += 1
    assert admitted == {0: 61, 64: 63, 128: 63, 192: 61}[start]


@pytest.mark.medium
@pytest.mark.parametrize(
    "kind", [pytest.param("dense", marks=pytest.mark.slow), "parity", "majority"]
)
def test_centered_eight_input_graphs_execute(kind, centered_check, tmp_path):
    table = (
        dense(8)
        if kind == "dense"
        else parity(8)
        if kind == "parity"
        else "".join(str(int(row.bit_count() > 4)) for row in range(256))
    )
    area, commands = centered_check(table, tmp_path)
    assert (
        area == {"dense": 37_795_200, "parity": 1_534_400, "majority": 3_982_400}[kind]
    )
    assert commands == {"dense": 23, "parity": 27, "majority": 23}[kind]


@pytest.mark.medium
def test_centered_scaled_crossings(centered_check, tmp_path):
    centered_check(parity(7), tmp_path, scale=2)
