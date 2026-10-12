"""Essential streaming stems retain every read and native sharing bounds."""

import random

import pytest

from esolangs.languages.line.generator import line
from esolangs.languages.line.generator.forward import projected_streaming_canvas
from esolangs.languages.line.tests import test_boolean_line_forward as controls
from esolangs.runtime._evaluate import _evaluate


def _embed(core, kept, n):
    return "".join(
        core[
            sum(
                ((row >> (n - 1 - at)) & 1) << (len(kept) - 1 - i)
                for i, at in enumerate(kept)
            )
        ]
        for row in range(1 << n)
    )


@pytest.fixture
def projected_check(monkeypatch):
    monkeypatch.setattr(controls, "forward_canvas", projected_streaming_canvas)
    return controls._check  # noqa: SLF001


@pytest.mark.medium
def test_every_admitted_three_input_projection_executes(
    projected_check, tmp_path
) -> None:
    admitted = 0
    for value in range(256):
        table = f"{value:08b}"
        if projected_streaming_canvas(table, 10**9) is None:
            continue
        projected_check(table, tmp_path)
        admitted += 1
    assert admitted == 30


@pytest.mark.medium
@pytest.mark.parametrize("n", [4, 5, 6])
def test_ignored_prefix_middle_and_tail_reads_execute(
    n, projected_check, tmp_path
) -> None:
    for kept in ((0, 1, 2), (n - 3, n - 2, n - 1), (0, 2, n - 1)):
        projected_check(_embed("00010111", kept, n), tmp_path)


@pytest.mark.medium
def test_seeded_eight_input_controls_keep_the_smaller_layout(
    tmp_path, projected_check
) -> None:
    rng = random.Random(419)
    old_total = new_total = admitted = 0
    for index in range(22):
        k = 3 + index % 2
        kept = sorted(rng.sample(range(8), k))
        core = "00010111" if k == 3 else "0000000100010111"
        table = _embed(core, kept, 8)
        program = line(table)
        area = len(program.rows) * len(program.rows[0])
        old_area = 1_435_600 if k == 4 else 1_036_800
        if kept[-1] < 7:
            old_area += 148_000 if k == 4 else 128_000
        assert area <= old_area
        old_total += old_area
        new_total += area
        candidate = projected_streaming_canvas(table, old_area)
        if candidate is not None:
            checked_area, commands = projected_check(table, tmp_path)
            assert checked_area == area == candidate[1].area == 1_443_200
            assert commands == 17
            assert _evaluate("Line", program.to_png(), inputs=8) == table
            admitted += 1
    assert admitted == 6
    assert (old_total, new_total) == (28_852_400, 28_010_000)


def test_projection_declines_constants_and_tables_without_ignored_inputs() -> None:
    for table in ("00000000", "11111111", "01101001", "00110011"):
        assert projected_streaming_canvas(table, 10**9) is None
