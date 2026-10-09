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
    assert 'Language("Not A Language"' in gap.fix


def test_check_runs_the_formula_case_bounds_measures() -> None:
    nodes = new_language.quick_tests("SStack")
    assert nodes[-1].endswith("formulas_hold[SStack-3]")
    assert new_language.bounds("SStack", range(1, 2))[0][:4] == (1, 10, 23, 23)


def test_a_generator_language_needs_no_hand_sample() -> None:
    import esolangs
    from tests import samples

    program, stdin = samples._generated("SStack")  # noqa: SLF001
    assert esolangs.run("SStack", program, stdin=stdin) == "1"


def test_sources_names_the_interpreter_and_generator() -> None:
    assert new_language.sources("Smu") == [
        "src/esolangs/interpreters/stack_based/smu.py",
        "src/esolangs/tools/smu.py",
    ]
    # A package interpreter is its directory.
    (interpreter, _) = new_language.sources("Piet")
    assert interpreter == "src/esolangs/interpreters/stack_based/piet"
