"""The premises the hub, stub and operand rules rest on.

Hubs and stubs are placed by their trits, not fitted around the tables:
that needs the readouts to be a product set with the missing digits the
rules name.  The ``1`` and ``n`` stubs need their operands to compute the
answer for both last inputs.
"""

from __future__ import annotations

from functools import reduce
from itertools import product

from esolangs.languages.malbolge.generator import core, digits
from esolangs.languages.malbolge.generator.isa import _g
from esolangs.languages.malbolge.interpreter import _crazy


def _digit(value: int, k: int) -> tuple[int, int]:
    return value // 3 ** (2 * k) % 3, value // 3 ** (2 * k + 1) % 3


def test_readouts_are_the_product_of_their_digits() -> None:
    readouts = set(digits._readouts(digits._DIGITS_N))  # noqa: SLF001
    seen = [{_digit(r, k) for r in readouts} for k in range(5)]
    missing = [set(product(range(3), repeat=2)) - s for s in seen]
    assert len(readouts) == 8**5
    # Digit 1 (trits 2, 3) and digit 4 (the top) place hubs and the code;
    # digit 3 (trits 6, 7) places the operand stubs.
    assert missing[1] == {(2, 2)}
    assert missing[3] == {(1, 2)}
    assert missing[4] == {(0, 0)}


def test_operands_answer_both_inputs_exactly() -> None:
    cells = core._operand_cells()  # noqa: SLF001
    for lab, answers in (("1", (49, 49)), ("n", (49, 48))):
        below, middle, above = cells[lab]
        operand = core._chain(_g(middle), core._OPERAND_CHAIN)  # noqa: SLF001
        values = (_g(below), operand, _g(above))
        for x, answer in enumerate(answers):
            assert reduce(_crazy, values, 48 + x) == answer, (lab, x)


def test_every_label_owns_two_hubs() -> None:
    hubs = digits._hubs()  # noqa: SLF001
    assert sorted(hubs) == sorted(core._T_HUB_LABELS)  # noqa: SLF001
    assert len({v for vs in hubs.values() for v in vs}) == 8
