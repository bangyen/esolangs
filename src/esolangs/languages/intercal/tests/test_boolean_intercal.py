"""Executed tests for the INTERCAL Shannon-expression generator."""

import random
import re

import pytest

import esolangs
from esolangs.generation.helpers import (
    _validate_truth_table,
    constant_span_test,
)
from esolangs.languages.intercal import generator
from esolangs.languages.intercal.generator import PAIR, TEMPLATE_CHAR, intercal
from esolangs.languages.intercal.interpreter import run
from esolangs.runtime._evaluate import _evaluate
from tests.proofs._witnesses import _intercal_worst
from tests.support.generator_support import run_filled


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


def _five_input_sample() -> list[str]:
    """Return the sharing catalogue's 200 five-input tables, seed 0."""
    rng, found = random.Random(0), set[str]()
    while len(found) < 200:
        found.add(format(rng.getrandbits(32), "032b"))
    return sorted(found)


def _unshared(table: str) -> str:
    return intercal_plain(table, tuple(range(len(table).bit_length() - 1)))


def test_repeated_subexpressions_are_assigned_once() -> None:
    """Repeated expressions are named once; the tree stays in input order."""
    parity = "01101001100101101001011001101001"
    template = intercal(parity)
    assert [f".{name} <- " in template for name in range(7, 14)] == [True] * 6 + [False]
    assert len(template) < len(_unshared(parity)) // 2
    for tables, pinned in (
        ([f"{value:08b}" for value in range(256)], (74152, 64072)),
        (_five_input_sample(), (216624, 139920)),
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


@pytest.mark.parametrize(("cap", "n"), [(12, 7), (20, 8), (30, 8)])
@pytest.mark.medium
def test_names_past_the_cap_spill_to_arrays_and_execute(
    cap: int, n: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lowered variable cap spills the top names; every row still computes."""
    monkeypatch.setattr(generator, "_VARIABLE_MAX", cap)
    table = _intercal_worst(n)
    template = intercal(table)
    assert " SUB #" in template
    assert max(int(k) for k in re.findall(r"\.(\d+)", template)) <= cap
    assert "".join(_run(table, row) for row in range(1 << n)) == table


def test_spill_width_is_zero_at_the_cap_and_a_ceiling_root_past_it() -> None:
    """``_spill``: nothing past the cap -> 0; S past it -> ceil(sqrt(S))."""
    from esolangs.languages.intercal.generator import _VARIABLE_MAX, _spill

    assert _spill(_VARIABLE_MAX) == 0
    assert _spill(_VARIABLE_MAX + 288) == 17
    assert _spill(_VARIABLE_MAX + 289) == 17
    assert _spill(_VARIABLE_MAX + 295) == 18


def test_program_declares_one_array_per_spill_width_of_names() -> None:
    """289 names past the cap at width 17 declare 17 arrays, not 18."""
    from esolangs.languages.intercal.generator import _VARIABLE_MAX, _ZERO, _program

    program = _program(2, [(_VARIABLE_MAX + 289, _ZERO)], _ZERO, width=17)
    assert re.findall(r",(\d+) <- #17", program) == [str(j) for j in range(1, 18)]


@pytest.mark.medium
def test_every_name_of_the_widest_witness_is_a_legal_variable() -> None:
    """n = 21 needs names to .65830; INTERCAL variables stop at .65535."""
    program = intercal(_intercal_worst(21))
    assert max(int(k) for k in re.findall(r"\.(\d+)", program)) <= 65535
    widths = re.findall(r"^\S+ ,(\d+) <- #(\d+)$", program, re.M)
    assert [int(j) for j, _ in widths] == list(range(1, 18))
    assert {w for _, w in widths} == {"18"}
    assert max(int(i) for i in re.findall(r" SUB #(\d+)", program)) <= 18


@pytest.mark.parametrize("table", ["00"])
def test_narrow_balance_regime_edge_executes(table) -> None:
    """The smallest tables reaching an otherwise-untaken balance arm."""
    balanced = esolangs.generate("INTERCAL", table, balance=True)
    assert _evaluate("INTERCAL", balanced, inputs=len(table).bit_length() - 1) == table


def intercal_plain(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one order's template; level ``k`` selects input ``perm[k]``."""
    from esolangs.languages.intercal.generator import _Expr, _mux, _program

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
