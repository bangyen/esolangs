"""Native destination moves and residue-separated fork spacing."""

import pytest

from esolangs.generation.helpers import permute_truth_table
from esolangs.languages.line.generator import line
from esolangs.languages.line.generator.forward import destination_canvas, forward_canvas
from esolangs.languages.line.tests import test_boolean_line_forward as controls
from esolangs.languages.line.tests.test_boolean_line_forward import _check
from tests.support.witness_tables import dense, parity


@pytest.fixture
def destination_check(monkeypatch):
    monkeypatch.setattr(controls, "forward_canvas", destination_canvas)
    return _check


@pytest.mark.medium
def test_every_admitted_three_input_destination_graph_executes(
    destination_check, tmp_path
) -> None:
    admitted = 0
    for value in range(256):
        table = f"{value:08b}"
        if destination_canvas(table, 10**9) is None:
            continue
        destination_check(table, tmp_path)
        admitted += 1
    assert admitted == 82


@pytest.mark.medium
def test_adjacent_terminal_and_nonterminal_arm_profiles(
    destination_check, tmp_path
) -> None:
    profiles = [
        a + b for a in ("0000", "1111", "0110") for b in ("0000", "1111", "0110")
    ]
    executed = 0
    for a in profiles:
        for b in profiles:
            table = permute_truth_table(a + b, (3, 2, 1, 0))
            if destination_canvas(table, 10**9) is None:
                continue
            destination_check(table, tmp_path)
            executed += 1
    assert executed == 20


@pytest.mark.medium
@pytest.mark.parametrize("n", [7, 8, 9])
def test_public_majority_shares_destination_moves(
    n, destination_check, tmp_path
) -> None:
    table = "".join(str(int(row.bit_count() > n // 2)) for row in range(1 << n))
    area, commands = destination_check(table, tmp_path)
    assert area == {7: 9_345_600, 8: 10_665_600, 9: 13_438_400}[n]
    assert commands <= 5 * n
    public = line(table)
    assert len(public.rows) * len(public.rows[0]) <= area


@pytest.mark.medium
def test_dense_narrow_forks_keep_native_rails_separate(
    destination_check, tmp_path
) -> None:
    table = dense(8)
    area, _ = destination_check(table, tmp_path)
    assert area == 75_521_200
    assert area < forward_canvas(table, 10**9)[1].area
    assert destination_canvas(table, 21_252_000) is None


@pytest.mark.medium
def test_parity_keeps_the_smaller_arrival_layout(destination_check, tmp_path) -> None:
    table = parity(6)
    area, _ = destination_check(table, tmp_path)
    assert area == 6_466_800
    assert destination_canvas(table, forward_canvas(table, 10**9)[1].area) is None


@pytest.mark.medium
@pytest.mark.parametrize("kept", [(0, 2, 5), (1, 3, 4)])
def test_projected_destination_loader_executes_every_row(
    kept, destination_check, tmp_path
) -> None:
    table = "".join(
        str(sum((row >> (5 - bit)) & 1 for bit in kept) % 2) for row in range(64)
    )
    destination_check(table, tmp_path)


@pytest.mark.slow
def test_majority_22_destination_moves_obey_native_contract(
    destination_check, tmp_path
) -> None:
    n = 22
    table = "".join(str(int(row.bit_count() > n // 2)) for row in range(1 << n))
    rows = sorted(
        {
            0,
            len(table) - 1,
            *range(0, len(table), len(table) // 32),
            (1 << 11) - 1,
            (1 << 12) - 1,
            (1 << 13) - 1,
        }
    )
    area, commands = destination_check(table, tmp_path, rows)
    assert area == 53_875_200
    assert commands == 98
