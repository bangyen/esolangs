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
