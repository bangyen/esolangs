"""The Execution column's command formulas hold at small n, over every row.

Each was derived from its generator, not fitted: a fit from parity data
(brainfuck 69n + 41) was beaten by random tables, 458 > 455 at n=6.  An
``exact`` formula must also be reached here; ``bound`` only never exceeded.
"""

import copy
import tomllib
from fractions import Fraction

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from scripts.docs.resource_description import parse_descriptions
from scripts.docs.resource_evidence import PACKAGES, parse_bounds
from scripts.docs.resource_formula import expression_formula
from tests.proofs._ledger import load as load_ledger
from tests.proofs.execution import FORMULAS, measure
from tests.support.generator_support import CHECK
from tests.support.reference import REFERENCE


def test_every_formula_cell_is_checked() -> None:
    """Every bounded or exact Execution clause has a formula here, and back."""
    stated = {
        row.generator for row in load_ledger().rows if row.resources.execution.bounded
    }
    unchecked = sorted(stated - set(FORMULAS))
    assert not unchecked, f"{unchecked} state a bound with no FORMULAS row; {CHECK}"
    orphaned = sorted(set(FORMULAS) - stated)
    assert not orphaned, f"remove {orphaned} from FORMULAS: no stated bound"
    path = PACKAGES / LANGUAGES[REFERENCE].id / "language.toml"
    data = tomllib.loads(path.read_text())["resource_evidence"]
    for column, changes in (
        ("execution", {"exact": 1}),
        ("execution", {"arities": [1, 1]}),
        ("execution", {"arities": [True]}),
        ("execution", {"first": 0}),
        ("execution", {"unit": "bits"}),
        ("workspace", {"unit": "commands"}),
        ("scaling", {"unit": "bits"}),
        ("execution", {"witnesses": "other:tables"}),
        ("execution", {"construction": "other:generate"}),
        ("execution", {"expression": "__import__('os')"}),
        ("execution", {"expression": "bl(n).__class__"}),
        ("execution", {"provider": "builtins:eval"}),
        ("execution", {"unexpected": 0}),
    ):
        broken = copy.deepcopy(data)
        broken[column].update(changes)
        with pytest.raises(ValueError, match=r"resource|workspace|scaling|execution"):
            parse_bounds(REFERENCE, broken)
    for broken in (
        data | {"version": True},
        data | {"unknown": {}},
        data | {"construction": "other:generate"},
    ):
        with pytest.raises(ValueError, match="resource"):
            parse_bounds(REFERENCE, broken)
    broken = copy.deepcopy(data)
    broken["execution"]["expression"] = "0"
    bound = parse_bounds(REFERENCE, broken)["execution"]
    program = esolangs.generate(REFERENCE, "0110")
    commands, _ = measure(REFERENCE, "0110", program=program)
    with pytest.raises(AssertionError, match="bound"):
        assert commands <= bound.formula(2, program.source), "mutated execution bound"
    _check_arity_cases(data)
    _check_rational_arithmetic()
    _check_decimal_digits()
    _check_weighted_widths()
    _check_residual_counts()
    _check_bit_width_sums()
    _check_source_term_schema()


def _check_source_term_schema() -> None:
    terms = frozenset({"S"})
    for expression in ("2X", "2", "S(n)"):
        with pytest.raises(ValueError, match="resource expression"):
            expression_formula(expression, (terms, lambda _n, _p: {"S": 3}))

    for value in ({"R": 1}, {"S": 0.5}, {"S": True}):
        formula = expression_formula("2S", (terms, lambda _n, _p, value=value: value))
        with pytest.raises(ValueError, match="invalid source terms"):
            formula(1, "")


def _check_bit_width_sums() -> None:
    formula = expression_formula("bit_sum(n)")
    for count in range(513):
        assert formula(count, "") == sum(k.bit_length() for k in range(count))
    assert formula(1 << 1024, "") == 1023 * (1 << 1024) + 1
    for expression in ("bit_sum(-1)", "bit_sum(1/2)"):
        with pytest.raises(ValueError, match="non-negative integer"):
            expression_formula(expression)(1, "")


def _check_arity_cases(data: dict) -> None:
    data = copy.deepcopy(data)
    row = data["execution"]
    del row["expression"]
    row["cases"] = [
        {"through": 1, "expression": "29"},
        {"expression": "46n - 21"},
    ]
    row["first"] = 1
    row["unit"] = "commands"
    row["description"]["template"] = "{claim} {formula}"
    formula = parse_bounds(REFERENCE, data)["execution"].formula
    assert [formula(n, "") for n in (1, 2, 3)] == [29, 71, 117]
    assert "29 (n=1), 46n - 21 (n≥2) commands" in (
        parse_descriptions(data).execution.clause
    )
    data["execution"]["first"] = 2
    assert "29" not in parse_descriptions(data).execution.clause

    for cases in (
        [],
        [{"through": 1, "expression": "29"}],
        [{"through": True, "expression": "29"}, {"expression": "n"}],
        [
            {"through": 2, "expression": "29"},
            {"through": 1, "expression": "n"},
            {"expression": "2n"},
        ],
        [{"through": 1, "expression": "29"}, {"through": 2, "expression": "n"}],
        [{"through": 1, "expression": "29"}, {"expression": "__import__('os')"}],
    ):
        broken = copy.deepcopy(data)
        broken["execution"]["cases"] = cases
        with pytest.raises(ValueError, match="resource case"):
            parse_bounds(REFERENCE, broken)


def _check_rational_arithmetic() -> None:
    for expression, expected in (
        ("1/10+2/10", Fraction(3, 10)),
        ("T+⌈n/7⌉/2", 2**55 + 4),
        ("(1/3)/(1/9)", 3),
        ("3^(-2)", Fraction(1, 9)),
        ("(2/3)^(-2)", Fraction(9, 4)),
    ):
        assert expression_formula(expression)(55, "") == expected
    with pytest.raises(ValueError, match="exponent must be an integer"):
        expression_formula("2^(1/2)")(1, "")


def _check_decimal_digits() -> None:
    for expression, expected in (
        ("digits(0)", 1),
        ("digits(10^3-1)", 3),
        ("digits(10^3)", 4),
        ("digits(10^5000-1)", 5000),
        ("digits(10^5000)", 5001),
        ("digits(20/2)", 2),
        ("digits_sum(0)", 0),
        ("digits_sum(10)", 10),
        ("digits_sum(11)", 12),
        ("digits_sum(101)", 193),
    ):
        assert expression_formula(expression)(1, "") == expected
    for expression in (
        "digits(-1)",
        "digits(1/2)",
        "digits_sum(-1)",
        "digits_sum(1/2)",
    ):
        with pytest.raises(ValueError, match="non-negative integer"):
            expression_formula(expression)(1, "")


def _check_residual_counts() -> None:
    from esolangs.generation.decision import residual_count_bound

    for n in range(13):
        for constants, name in (
            (True, "residuals"),
            (False, "residuals_without_constants"),
        ):
            cap = sum(
                min(1 << depth, (1 << (1 << (n - depth))) - (0 if constants else 2))
                for depth in range(n)
            )
            assert expression_formula(f"{name}(n)")(n, "") == cap
    # An unconditional first-level tower cannot be built at this arity.
    assert (
        residual_count_bound(1024) - residual_count_bound(1024, include_constants=False)
        == 18
    )
    for expression in ("residuals(-1)", "residuals_without_constants(1/2)"):
        with pytest.raises(ValueError, match="non-negative integer"):
            expression_formula(expression)(1, "")


def _check_weighted_widths() -> None:
    power_digits = expression_formula("power2_digits_sum(n)")
    weighted_bits = expression_formula("weighted_bit_sum(n)")
    for n in range(65):
        assert power_digits(n, "") == sum(len(str(1 << k)) for k in range(n))
        assert weighted_bits(n, "") == sum(
            k.bit_length() << (n - k) for k in range(1, n + 1)
        )
    for expression in ("power2_digits_sum(-1)", "weighted_bit_sum(1/2)"):
        with pytest.raises(ValueError, match="non-negative integer"):
            expression_formula(expression)(1, "")
