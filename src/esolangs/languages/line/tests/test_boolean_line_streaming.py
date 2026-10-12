"""Native input-order reads, constant drains, and shared streaming joins."""

import pytest

from esolangs.languages.line.generator import line
from esolangs.languages.line.generator.forward import streaming_canvas
from esolangs.languages.line.tests import test_boolean_line_forward as controls
from esolangs.languages.line.tests.test_boolean_line_forward import _check
from esolangs.runtime._evaluate import _evaluate
from tests.support.witness_tables import dense, parity


@pytest.fixture
def streaming_check(monkeypatch):
    monkeypatch.setattr(controls, "forward_canvas", streaming_canvas)
    return _check


@pytest.mark.medium
@pytest.mark.parametrize(
    ("start", "expected"), [(0, 61), (64, 63), (128, 63), (192, 61)]
)
def test_every_admitted_three_input_stream_executes(
    start, expected, streaming_check, tmp_path
) -> None:
    admitted = 0
    for value in range(start, start + 64):
        table = f"{value:08b}"
        if streaming_canvas(table, 10**9) is None:
            continue
        streaming_check(table, tmp_path)
        admitted += 1
    assert admitted == expected


@pytest.mark.medium
def test_two_input_streams_fit_the_smallest_command_bound(
    streaming_check, tmp_path
) -> None:
    admitted = 0
    for value in range(16):
        table = f"{value:04b}"
        if streaming_canvas(table, 10**9) is None:
            continue
        streaming_check(table, tmp_path)
        admitted += 1
    assert admitted == 10


@pytest.mark.medium
@pytest.mark.parametrize(
    "kind", [pytest.param("dense", marks=pytest.mark.slow), "parity", "majority"]
)
def test_eight_input_streams_execute_all_rows(kind, streaming_check, tmp_path) -> None:
    table = (
        dense(8)
        if kind == "dense"
        else parity(8)
        if kind == "parity"
        else "".join(str(int(row.bit_count() > 4)) for row in range(256))
    )
    area, commands = streaming_check(table, tmp_path)
    assert (
        area == {"dense": 42_265_600, "parity": 1_534_400, "majority": 3_952_000}[kind]
    )
    assert commands == {"dense": 23, "parity": 27, "majority": 23}[kind]
    public = line(table)
    assert len(public.rows) * len(public.rows[0]) <= area
    assert _evaluate("Line", public.to_png(), inputs=8) == table
    if kind == "dense":
        assert streaming_canvas(table, 21_252_000) is None


@pytest.mark.medium
@pytest.mark.parametrize("kept", [(0, 1), (1, 4), (4, 5)])
def test_ignored_inputs_and_constant_drains(kept, streaming_check, tmp_path) -> None:
    table = "".join(
        str(int(all(row >> (5 - bit) & 1 for bit in kept))) for row in range(64)
    )
    streaming_check(table, tmp_path)


@pytest.mark.medium
def test_scaled_streaming_crossings(streaming_check, tmp_path) -> None:
    streaming_check(parity(7), tmp_path, scale=2)


def test_constant_and_single_input_tables_keep_existing_layout() -> None:
    for table in ("00000000", "11111111", "01", "10"):
        assert streaming_canvas(table, 10**9) is None


@pytest.mark.medium
def test_adjacent_constant_and_test_free_reader_profiles(
    streaming_check, tmp_path
) -> None:
    profiles = [
        a + b for a in ("0000", "1111", "0110") for b in ("0000", "1111", "0110")
    ]
    admitted = 0
    for a in profiles:
        for b in profiles:
            table = a + b
            if streaming_canvas(table, 10**9) is None:
                continue
            streaming_check(table, tmp_path)
            admitted += 1
    assert admitted > 0
