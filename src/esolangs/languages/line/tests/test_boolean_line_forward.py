"""Native controls for descending residual stems and forward joins."""

import random

import pytest

from esolangs.languages.line.generator import line
from esolangs.languages.line.generator.forward import forward_canvas
from esolangs.languages.line.interpreter.extract import extract
from esolangs.languages.line.interpreter.simulate import (
    IO,
    _advance,
    _freeze_program,
    compile_program,
    run_node,
)
from esolangs.runtime._evaluate import _evaluate
from scripts.benchmark import WrittenState


def _check(table, tmp_path, rows=None, scale=1):
    built = forward_canvas(table, 10**9)
    assert built is not None
    graph, plan = built
    canvas = plan()
    assert canvas.width * canvas.height == plan.area
    assert forward_canvas(table, plan.area) is None
    canvas = canvas.upscale(scale)
    path = str(tmp_path / "forward.png")
    canvas.save(path)
    frames = _freeze_program(compile_program(extract(path)))
    n = len(table).bit_length() - 1
    bound = n + 1 + (3 * n - 2).bit_length() + (n - 1).bit_length()
    bound += (2 * n - 1).bit_length() + sum(
        max(1, cell.bit_length()) + 1 for cell in range(n)
    )
    maximum = 0
    for row in range(1 << n) if rows is None else rows:
        inputs = [(row >> shift) & 1 for shift in range(n - 1, -1, -1)]
        values = iter(inputs)
        output = []
        run_node(graph, IO(read=values.__next__, write=output.append))
        assert output == [int(table[row])]
        values = iter(inputs)
        state = (0, 0, 0, ())
        written = WrittenState((0, 0, 0, (), 0))
        output = []
        reads = commands = 0
        while state[0] is not None:
            frame = frames[state[0]]
            at = state[1]
            value = (
                next(values)
                if at < len(frame.ops) and frame.ops[at][0] == "i"
                else None
            )
            reads += value is not None
            state, value = _advance(state, frames, value)
            if value is not None:
                output.append(value)
            commands += 1
            assert commands <= 5 * n
            node, at, pointer, tape = state
            assert all(0 <= cell < n and value in (0, 1) for cell, value in tape)
            written.sample(
                (
                    node,
                    at,
                    pointer,
                    tuple((cell, value) for cell, value in tape if value),
                    max(0, 2 * reads - 1),
                )
            )
        assert reads == n
        assert output == [int(table[row])]
        assert written.bits <= bound
        maximum = max(maximum, commands)
    return plan.area, maximum


@pytest.mark.medium
def test_every_admitted_three_input_residual_dag_executes(tmp_path) -> None:
    admitted = 0
    for value in range(256):
        table = f"{value:08b}"
        if forward_canvas(table, 10**9) is not None:
            _check(table, tmp_path)
            admitted += 1
    assert admitted == 82


@pytest.mark.medium
@pytest.mark.parametrize("n", [6, 7, 8])
def test_parity_shares_same_level_residuals_within_existing_contract(
    n, tmp_path
) -> None:
    table = "".join(str(row.bit_count() % 2) for row in range(1 << n))
    area, commands = _check(table, tmp_path)
    assert area == {6: 5_094_000, 7: 5_922_000, 8: 6_750_000}[n]
    assert area < {6: 5_328_000, 7: 14_280_000, 8: 17_472_000}[n]
    assert commands == 5 * n - 1


@pytest.mark.medium
@pytest.mark.parametrize("n", [8, 9])
def test_public_majority_shares_residuals_and_executes_every_row(n, tmp_path) -> None:
    table = "".join(str(int(row.bit_count() > n // 2)) for row in range(1 << n))
    area, _ = _check(table, tmp_path)
    assert area == {8: 12_028_800, 9: 16_723_200}[n]
    assert area < {8: 13_920_000, 9: 28_492_800}[n]
    public = line(table)
    assert len(public.rows) * len(public.rows[0]) <= area
    assert _evaluate("Line", public.to_png(), inputs=n) == table


@pytest.mark.medium
def test_scaled_crossings_and_joins_execute_every_row(tmp_path) -> None:
    table = "".join(str(row.bit_count() % 2) for row in range(128))
    _check(table, tmp_path, scale=2)


@pytest.mark.medium
@pytest.mark.parametrize("seed", [0, 1, 3])
def test_dense_residuals_join_after_tests_and_test_free_levels(seed, tmp_path) -> None:
    rng = random.Random(seed)
    table = "".join(rng.choice("01") for _ in range(32))
    _check(table, tmp_path)


@pytest.mark.medium
@pytest.mark.parametrize("kept", [(0, 1, 2), (1, 2, 3), (3, 4, 5), (0, 2, 5)])
def test_projected_loader_preserves_order_and_original_workspace(
    kept, tmp_path
) -> None:
    core = "00010111"
    table = "".join(
        core[sum(((row >> (5 - at)) & 1) << (2 - i) for i, at in enumerate(kept))]
        for row in range(64)
    )
    _check(table, tmp_path)


def test_constants_and_unshared_graphs_keep_existing_layout() -> None:
    for table in ("00000000", "11111111", "01", "0001"):
        assert forward_canvas(table, 10**9) is None
