"""ArrowQueue's narrow cascade preserves the termination answer."""

import pytest

import esolangs
from esolangs.languages.arrowqueue.generator import arrowqueue
from tests.generators.fills import fill
from tests.support.divergence import diverges
from tests.support.witness_tables import row_bits

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


@pytest.mark.parametrize("width", [4, 5, 6])
def test_a_narrow_template_fills_against_its_table(width: int) -> None:
    """Width 5 shifts the setter column and was refused as a foreign template."""
    template = esolangs.generate("ArrowQueue", "0110", width=width)
    program = esolangs.instantiate("ArrowQueue", template, [0, 1], truth_table="0110")
    assert diverges("ArrowQueue", program, "") is True


@pytest.mark.parametrize("width", [1, 4, 5, 6])
def test_arrowqueue_narrow_drops_ignored_inputs(width: int) -> None:
    """A narrow build with ignored inputs is smaller than the full cascade and runs."""
    from esolangs.runtime._evaluate import _evaluate

    table = "".join(b for b in "0110" for _ in range(8))  # 2 of 5 inputs essential
    template = arrowqueue(table, width)
    assert _evaluate("ArrowQueue", template, inputs=5) == table
    full = arrowqueue("".join(str(bin(i).count("1") % 2) for i in range(32)), width)
    assert template.count("\n") < full.count("\n")


@pytest.mark.parametrize(
    "table", ["0001", "0110", "10010110", "0110" * 4, "01" * 16, "0110100110010110"]
)
def test_balanced_fold_computes_every_row_and_is_squarer(table: str) -> None:
    """The folded cascade beats the unfolded candidates and keeps the answer."""
    from esolangs.generation.wrap import balance_score
    from esolangs.runtime._evaluate import _evaluate

    program = str(esolangs.generate("ArrowQueue", table, balance=True))
    inputs = len(table).bit_length() - 1
    assert _evaluate("ArrowQueue", program, inputs=inputs) == table
    flat = min((arrowqueue(table, w) for w in (None, 1, 5, 6)), key=balance_score)
    assert balance_score(program)[0] < balance_score(flat)[0]


@pytest.mark.parametrize(
    ("table", "rows", "cols", "chars"),
    [
        ("11101111", 10, 26, 245),
        ("01000100", 10, 21, 180),
        ("01011010", 26, 5, 133),
    ],
)
def test_balanced_three_input_sizes_are_pinned(
    table: str, rows: int, cols: int, chars: int
) -> None:
    """Balanced 3-input programs keep their measured shape and still compute."""
    from esolangs.runtime._evaluate import _evaluate

    program = str(esolangs.generate("ArrowQueue", table, balance=True))
    lines = program.split("\n")
    assert (len(lines), max(map(len, lines)), len(program)) == (rows, cols, chars)
    assert _evaluate("ArrowQueue", program, inputs=3) == table


def test_fold_heights_stay_near_the_swept_optimum() -> None:
    """Four heights from a closed form are within 5% of every height (sum)."""
    import random

    from esolangs.generation.wrap import balance_score
    from esolangs.languages.arrowqueue.generator import _folded, _folds

    rng = random.Random(11)
    got = swept = 0
    for n in range(3, 9):
        for _ in range(4):
            table = "".join(rng.choice("01") for _ in range(1 << n))
            if len(set(table)) == 1:
                continue
            limit = 6 * n + len(table) + 12
            every = (_folded(table, h) for h in range(10, limit))
            swept += min(balance_score(f)[0] for f in every if f is not None)
            got += min(balance_score(f)[0] for f in _folds(table))
    assert swept <= got <= 1.05 * swept
