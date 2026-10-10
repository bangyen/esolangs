"""SStack through the shared API, CLI and machinery."""

from scripts import new_language


def test_check_runs_the_formula_case_bounds_measures() -> None:
    nodes = new_language.quick_tests("SStack")
    assert nodes[-1].endswith("formulas_hold[SStack-3]")
    assert new_language.bounds("SStack", range(1, 2))[0][:4] == (1, 9, 23, 19)
