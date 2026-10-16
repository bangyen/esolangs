"""Piet's raster balancing is measured on rendered, executable images."""

import pytest

import esolangs
from esolangs.generation.raster_lookup.balance import (
    _bounded_operations,
    _emit,
    _plan,
    _tight_plan,
)
from esolangs.raster import Raster
from tests.support.witness_tables import witnesses

pytestmark = pytest.mark.medium

TABLES = list(dict.fromkeys(witnesses(1) + witnesses(2)))


def score(image: Raster) -> tuple[int, int, int]:
    width, height = len(image.rows[0]), len(image.rows)
    return abs(width - height), width * height, width


def test_piet_invalid_plans_abort() -> None:
    operations = _bounded_operations("01101001")
    with pytest.raises(AssertionError, match="no room"):
        _plan(operations, 5, 6)
    plan = _plan(operations, 13, 14)
    with pytest.raises(AssertionError, match="exceeds"):
        _emit(operations, plan._replace(width=1))
    overlapping = plan._replace(rows=[plan.rows[0]._replace(x=0), *plan.rows[1:]])
    with pytest.raises(AssertionError, match="overwrites"):
        _emit(operations, overlapping)
    shifted = plan._replace(
        rows=[plan.rows[0], plan.rows[1]._replace(x=plan.rows[1].x + 1), *plan.rows[2:]]
    )
    with pytest.raises(AssertionError, match="turn model"):
        _emit(operations, shifted)


@pytest.mark.parametrize("width", [14, 19, 30])
def test_dense_bends_and_final_halt_execute(width: int) -> None:
    table = "01101001"
    operations = _bounded_operations(table)
    plan = _plan(operations, width, width + 1, compact=True, dense=True)
    assert all(
        b.y - a.y == 2 for a, b in zip(plan.rows[:-2], plan.rows[1:-1], strict=True)
    )
    assert plan.rows[-1].y - plan.rows[-2].y >= 3
    program = Raster.from_png(_emit(operations, plan).to_png())
    for row in range(8):
        assert (
            esolangs.run(
                "Piet", program, stdin="\n".join(f"{row:03b}") + "\n", max_steps=1000
            )
            == table[row]
        )


@pytest.mark.parametrize("width", [13, 19, 30])
def test_tight_routing_never_grows_and_executes(width: int) -> None:
    for inputs in (1, 2, 3):
        for encoded in range(2 ** (2**inputs)):
            table = f"{encoded:0{2**inputs}b}"
            operations = _bounded_operations(table)
            old = _plan(operations, width, width + 1, compact=True)
            plan = _tight_plan(operations, width, width + 1)
            assert plan.width * plan.height <= old.width * old.height
            program = Raster.from_png(_emit(operations, plan).to_png())
            for row in range(2**inputs):
                assert (
                    esolangs.run(
                        "Piet",
                        program,
                        stdin="\n".join(f"{row:0{inputs}b}") + "\n",
                        max_steps=2000,
                    )
                    == table[row]
                )


@pytest.mark.parametrize(
    ("duplicate", "short", "width"),
    [(False, False, width) for width in (22, 40)]
    + [(True, False, width) for width in (18, 30)]
    + [(True, True, width) for width in (18, 40)],
)
def test_white_bridge_lanes_execute_exhaustively(
    *, duplicate: bool, short: bool, width: int
) -> None:
    from esolangs.generation.raster_lookup.packing import _layout

    for inputs in (1, 2, 3):
        for encoded in range(2 ** (2**inputs)):
            table = f"{encoded:0{2**inputs}b}"
            program = Raster.from_png(
                _layout(
                    _bounded_operations(table), width, duplicate=duplicate, short=short
                ).to_png()
            )
            for row in range(2**inputs):
                assert (
                    esolangs.run(
                        "Piet",
                        program,
                        stdin="\n".join(f"{row:0{inputs}b}") + "\n",
                        max_steps=3000,
                    )
                    == table[row]
                )


@pytest.mark.parametrize(
    "table",
    [
        "11011010101101011010111100100001111110111101101001010001000110101100"
        "000011101011101000111001100110110001110011000100011010010001",
        "1000011010111001100111010010000110000101001000100010110110101000"
        "0000001111001010011111001101001100011011110110000010110100100001"
        "0010111110101001011011110011101001000011010111001101100011100001"
        "1011001110100001100110011101001011010111110000100110100110011010",
    ],
)
def test_white_bridge_turn_colors_and_halt_execute(table: str) -> None:
    from esolangs.generation.raster_lookup.balance import _balanced_plan
    from esolangs.generation.raster_lookup.packing import pack
    from esolangs.languages.piet.interpreter import BLACK, WHITE

    operations = _bounded_operations(table)
    default = esolangs.generate("Piet", table)
    old = _emit(
        operations, _balanced_plan(operations, default, compact=True, dense=True)
    )
    program = Raster.from_png(pack(operations, old).to_png())
    assert any(pixel == WHITE for row in program.rows for pixel in row)
    assert score(program)[1] < score(old)[1]
    assert sum(pixel == BLACK for row in program.rows for pixel in row) < sum(
        pixel == BLACK for row in old.rows for pixel in row
    )
    inputs = len(table).bit_length() - 1
    for row in range(len(table)):
        assert (
            esolangs.run(
                "Piet",
                program,
                stdin="\n".join(f"{row:0{inputs}b}") + "\n",
                max_steps=10000,
            )
            == table[row]
        )


def test_packed_routing_invariant_failures_abort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from esolangs.generation.raster_lookup import _INITIAL, packing
    from esolangs.generation.raster_lookup.packing import _lanes, _layout, _put

    with pytest.raises(AssertionError, match="no room"):
        _lanes(_bounded_operations("01101001"), 5)
    with pytest.raises(AssertionError, match="overlap"):
        _put({}, {(0, 0): (_INITIAL, 0)}, 1, 0, 0, _INITIAL)
    monkeypatch.setattr(packing, "_next_colour", lambda _colour, _change: _INITIAL)
    with pytest.raises(AssertionError, match="cannot isolate"):
        _layout(_bounded_operations("01101001"), 22)
