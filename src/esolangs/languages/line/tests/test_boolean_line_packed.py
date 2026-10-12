"""Native controls for packed streamed arrivals and joins."""

import pytest

from esolangs.languages.line.generator import line
from esolangs.languages.line.generator.forward import packed_streaming_canvas
from esolangs.languages.line.tests import test_boolean_line_forward as controls
from esolangs.languages.line.tests.test_boolean_line_forward import _check
from esolangs.languages.line.tests.test_boolean_line_projection import _execute
from esolangs.languages.line.tests.test_boolean_line_share_scope import _sample
from tests.support.witness_tables import dense, parity


@pytest.fixture
def packed_check(monkeypatch):
    monkeypatch.setattr(controls, "forward_canvas", packed_streaming_canvas)
    return _check


@pytest.mark.medium
@pytest.mark.parametrize("start", [0, 64, 128, 192])
def test_packed_three_input_graphs_execute(start, packed_check, tmp_path):
    admitted = 0
    for value in range(start, start + 64):
        table = f"{value:08b}"
        if packed_streaming_canvas(table, 10**9) is not None:
            packed_check(table, tmp_path)
            admitted += 1
    assert admitted == {0: 61, 64: 63, 128: 63, 192: 61}[start]


@pytest.mark.medium
@pytest.mark.parametrize(
    "kind", [pytest.param("dense", marks=pytest.mark.slow), "parity", "majority"]
)
def test_packed_eight_input_graphs_execute(kind, packed_check, tmp_path):
    table = (
        dense(8)
        if kind == "dense"
        else parity(8)
        if kind == "parity"
        else "".join(str(int(row.bit_count() > 4)) for row in range(256))
    )
    area, commands = packed_check(table, tmp_path)
    assert (
        area == {"dense": 36_169_600, "parity": 1_534_400, "majority": 4_164_800}[kind]
    )
    assert commands == {"dense": 23, "parity": 27, "majority": 23}[kind]


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "index", "area", "old"),
    [(6, 39, 5_505_600, 5_555_200), (7, 2, 14_212_800, 14_313_600)],
)
def test_public_packed_improvements_execute(
    n, index, area, old, packed_check, tmp_path
):
    table = _sample(n, index + 1, 11 + n)[index]
    measured, _ = packed_check(table, tmp_path)
    assert measured == area < old
    generated = line(table)
    assert len(generated.rows) * len(generated.rows[0]) <= area
    _execute(table, generated, range(1 << n))


@pytest.mark.medium
def test_packed_scaled_crossings(packed_check, tmp_path):
    packed_check(parity(7), tmp_path, scale=2)


def test_packed_excessive_layer_work_rejects_before_routing(monkeypatch):
    from importlib import import_module

    forward = import_module("esolangs.languages.line.generator.forward")

    def unexpected(*_args, **_kwargs):
        raise AssertionError("routing exceeded its work budget")

    monkeypatch.setattr(forward, "_join_lanes", unexpected)
    assert packed_streaming_canvas(dense(12), 10**9) is None
