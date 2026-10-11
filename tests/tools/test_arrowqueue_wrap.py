"""ArrowQueue's narrow cascade preserves the termination answer."""

import pytest

import esolangs
from esolangs.tools.arrowqueue import arrowqueue
from tests.support.divergence import diverges
from tests.support.witness_tables import row_bits
from tests.tools.fills import fill

_instantiate_arrowqueue = fill("ArrowQueue")


# 80 builds what None does.
@pytest.mark.parametrize("width", [1, 5, None])
@pytest.mark.parametrize(
    "table",
    ["0110", "00010111", "01101001" * 4],
)
def test_arrowqueue_width_preserves_every_row(table: str, width: int | None) -> None:
    template = esolangs.generate("ArrowQueue", table, width=width)
    plain = arrowqueue(table)
    if width is None:
        assert template == plain
    else:
        assert max(map(len, template.splitlines())) <= max(4, width)
    inputs = len(table).bit_length() - 1
    for row, expected in enumerate(table):
        bits = row_bits(row, inputs)
        source = _instantiate_arrowqueue(template, bits)
        assert diverges("ArrowQueue", source, "") is (expected == "1")


@pytest.mark.parametrize("tagged", [False, True])
def test_arrowqueue_four_columns_preserve_public_provenance(*, tagged: bool) -> None:
    table = "0110"
    template = esolangs.generate("ArrowQueue", table, width=1)
    source = template if tagged else str(template)
    for row, expected in enumerate(table):
        bits = [row >> 1, row & 1]
        program = esolangs.instantiate("ArrowQueue", source, bits, truth_table=table)
        assert max(map(len, program.splitlines())) == 4
        assert diverges("ArrowQueue", program, "") is (expected == "1")
    with pytest.raises(ValueError, match="does not compute that table"):
        esolangs.instantiate("ArrowQueue", source, [0, 1], truth_table="1001")


@pytest.mark.parametrize("width", [1, 4, 5, 6])
def test_arrowqueue_narrow_drops_ignored_inputs(width: int) -> None:
    """A narrow build with ignored inputs is smaller than the full cascade and runs."""
    from esolangs._evaluate import _evaluate

    table = "".join(b for b in "0110" for _ in range(8))  # 2 of 5 inputs essential
    template = arrowqueue(table, width)
    assert _evaluate("ArrowQueue", template, inputs=5) == table
    full = arrowqueue("".join(str(bin(i).count("1") % 2) for i in range(32)), width)
    assert template.count("\n") < full.count("\n")
