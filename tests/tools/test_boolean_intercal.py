"""Executed tests for the INTERCAL Shannon-expression generator."""

import random
from itertools import pairwise

from esolangs.tools.helpers import best_input_order
from esolangs.tools.intercal import PAIR, TEMPLATE_CHAR, intercal
from tests.tools.plain_oracles import intercal_plain as _intercal_ordered


def test_setters_are_equal_width_and_embedded_once() -> None:
    assert len(PAIR[0]) == len(PAIR[1]) == 2
    for n in range(1, 8):
        template = intercal("01" * (1 << (n - 1)))
        assert template.count(TEMPLATE_CHAR) == 2 * n


def test_source_growth_is_linear() -> None:
    sizes = [len(intercal("0110" * (1 << (n - 2)))) for n in range(2, 11)]
    assert all(right <= 2 * left + 500 for left, right in pairwise(sizes))


def test_levels_select_inputs_in_the_shorter_order() -> None:
    """Assignments stay in name order; only the selectors move.

    ``10101010`` depends on input 2 (``.1``) alone: split on it first, the
    expression names ``.1`` and nothing else.  Over all three-input tables
    no template grows and the total falls 11.4%.
    """
    template = intercal("10101010")
    assert template.index(".3 <- @@") < template.index(".1 <- @@")
    expression = template.split(".4 <- ", 1)[1].split("\n", 1)[0]
    assert {name for name in (".1", ".2", ".3") if name in expression} == {".1"}
    old = new = 0
    for value in range(256):
        table = f"{value:08b}"
        before = len(_intercal_ordered(table, (0, 1, 2)))
        after = len(_unshared(table))
        assert after <= before, table
        old, new = old + before, new + after
    assert (old, new) == (74152, 65704)


def _five_input_sample() -> list[str]:
    """Return ``scripts/screens/sharing.py``'s 200 five-input tables, seed 0."""
    rng, found = random.Random(0), set[str]()
    while len(found) < 200:
        found.add(format(rng.getrandbits(32), "032b"))
    return sorted(found)


def _unshared(table: str) -> str:
    return best_input_order(table, _intercal_ordered)


def test_repeated_subexpressions_are_assigned_once() -> None:
    """Repeated expressions are named once; the tree stays in input order."""
    parity = "01101001100101101001011001101001"
    template = intercal(parity)
    assert [f".{name} <- " in template for name in range(7, 14)] == [True] * 6 + [False]
    assert len(template) < len(_unshared(parity)) // 2
    for tables, pinned in (
        ([f"{value:08b}" for value in range(256)], (65704, 64072)),
        (_five_input_sample(), (195636, 139920)),
    ):
        old = new = 0
        for table in tables:
            before, after = len(_unshared(table)), len(intercal(table))
            old, new = old + before, new + after
        assert (old, new) == pinned
