"""Executed tests for the INTERCAL Shannon-expression generator."""

import random

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.interpreters.other.intercal import run
from esolangs.tools.helpers import (
    _validate_truth_table,
    best_input_order,
    constant_span_test,
)
from esolangs.tools.intercal import PAIR, TEMPLATE_CHAR, intercal
from tests.generator_support import run_filled


def _run(table: str, row: int) -> str:
    n = len(table).bit_length() - 1
    output = run_filled(run, intercal(table), [PAIR] * n, row, n, TEMPLATE_CHAR)
    assert output in {"_\n\n", "I\n"}
    return "1" if output == "I\n" else "0"


def test_setters_are_equal_width_and_embedded_once() -> None:
    assert len(PAIR[0]) == len(PAIR[1]) == 2
    for n in range(1, 8):
        template = intercal("01" * (1 << (n - 1)))
        assert template.count(TEMPLATE_CHAR) == 2 * n


def test_levels_select_inputs_in_the_shorter_order() -> None:
    """Assignments stay in name order; only the selectors move."""
    template = intercal("10101010")
    assert template.index(".3 <- @@") < template.index(".1 <- @@")
    expression = template.split(".4 <- ", 1)[1].split("\n", 1)[0]
    assert {name for name in (".1", ".2", ".3") if name in expression} == {".1"}
    old = new = 0
    for value in range(256):
        table = f"{value:08b}"
        before = len(intercal_plain(table, (0, 1, 2)))
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
    return best_input_order(table, intercal_plain)


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


@pytest.mark.parametrize("n", range(4, 7))
@pytest.mark.medium
def test_shared_templates_execute_on_sampled_tables(n: int) -> None:
    rng = random.Random(n)
    for _ in range(3):
        table = format(rng.getrandbits(1 << n), f"0{1 << n}b")
        assert "".join(_run(table, row) for row in range(1 << n)) == table


@pytest.mark.parametrize("table", ["00"])
def test_narrow_balance_regime_edge_executes(table):
    """The smallest tables reaching an otherwise-untaken balance arm."""
    balanced = esolangs.generate("INTERCAL", table, balance=True)
    assert _evaluate("INTERCAL", balanced, inputs=len(table).bit_length() - 1) == table


def intercal_plain(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one order's template; level ``k`` selects input ``perm[k]``."""
    from esolangs.tools.intercal import _Expr, _mux, _program

    n = _validate_truth_table(truth_table)
    constant = constant_span_test(truth_table)

    def tree(level: int, lo: int, hi: int) -> _Expr:
        if constant(lo, hi):
            return _Expr("constant", int(truth_table[lo]))
        mid = (lo + hi) // 2
        # In name order large variable numbers occur near the root, where
        # their decimal spelling is repeated least; this keeps source size
        # linear in T.  A reorder moves them only through the greedy cap
        # (n = 10), where no name is longer than two digits.
        zero, one = tree(level + 1, lo, mid), tree(level + 1, mid, hi)
        return _mux(_Expr("input", n - 1 - perm[level]), zero, one)

    return _program(n, [], tree(0, 0, len(truth_table)))
