"""The Execution column's command formulas hold at small n, over every row.

Each was derived from its generator, not fitted: a fit from parity data
(brainfuck 69n + 41) was beaten by random tables, 458 > 455 at n=6.  An
``exact`` formula must also be reached here; ``bound`` only never exceeded.
"""

import copy
import tomllib

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from scripts.docs.resource_evidence import PACKAGES, parse_bounds
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
    for broken in (data | {"version": True}, data | {"unknown": {}}):
        with pytest.raises(ValueError, match="resource"):
            parse_bounds(REFERENCE, broken)
    broken = copy.deepcopy(data)
    broken["execution"]["expression"] = "0"
    bound = parse_bounds(REFERENCE, broken)["execution"]
    program = esolangs.generate(REFERENCE, "0110")
    commands, _ = measure(REFERENCE, "0110", program=program)
    with pytest.raises(AssertionError, match="bound"):
        assert commands <= bound.formula(2, program.source), "mutated execution bound"
