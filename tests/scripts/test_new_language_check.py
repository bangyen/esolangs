"""``new_language.py check`` agrees with the suite on every registered language."""

import pytest

from esolangs.registry import LANGUAGES
from scripts import new_language


@pytest.mark.medium
def test_every_registered_language_passes_check() -> None:
    """A step ``check`` asks for that a shipped language lacks is a stale step."""
    gaps = {name: new_language.check(name) for name in LANGUAGES}
    assert not {name: g for name, g in gaps.items() if g}


def test_an_unregistered_language_is_told_to_register() -> None:
    (gap,) = new_language.check("Not A Language")
    assert gap.where == "src/esolangs/registry/_table.py"
    assert 'id="not_a_language"' in gap.fix


def test_check_runs_the_formula_case_bounds_measures() -> None:
    nodes = new_language.quick_tests("SStack")
    assert nodes[-1].endswith("formulas_hold[SStack-3]")
    assert new_language.bounds("SStack", range(1, 2)) == [(1, 10, 23)]
