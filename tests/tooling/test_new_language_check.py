"""``new_language.py check`` agrees with the suite on every registered language."""

import inspect
from pathlib import Path

import pytest

from esolangs.registry import LANGUAGES
from scripts import new_language
from tests.support.pick import first


@pytest.mark.medium
def test_every_registered_language_passes_check() -> None:
    """A step ``check`` asks for that a shipped language lacks is a stale step."""
    gaps = {name: new_language.check(name) for name in LANGUAGES}
    assert not {name: g for name, g in gaps.items() if g}


def test_an_unregistered_language_is_told_to_register() -> None:
    (gap,) = new_language.check("Not A Language")
    assert gap.where == "src/esolangs/registry/_table.py"
    assert 'Language("Not A Language"' in gap.fix


_LONGEST = max(LANGUAGES, key=len)


def test_a_misspelled_name_is_refused_with_a_suggestion(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A typo would otherwise read as a new language to register."""
    with pytest.raises(SystemExit):
        new_language.main(["check", _LONGEST[:-1]])
    assert _LONGEST in capsys.readouterr().err


def test_a_name_resolves_like_the_api_and_a_new_one_passes() -> None:
    registered = new_language._registered_name  # noqa: SLF001
    assert registered(_LONGEST.swapcase()) == _LONGEST
    assert registered("Not A Language") == "Not A Language"


def test_a_generator_language_needs_no_hand_sample() -> None:
    import esolangs
    from tests.support import samples

    name = first(boolean_generator=True, parameterized=False, answer_mode="output")
    program, stdin = samples._generated(name)  # noqa: SLF001
    assert esolangs.read_answer(name, esolangs.run(name, program, stdin=stdin)) == "1"


def test_sources_names_the_interpreter_and_generator() -> None:
    for name, lang in LANGUAGES.items():
        if lang.interpreter is None or lang.boolean is None:
            continue
        found = new_language.sources(name)
        interpreter = f"src/esolangs/languages/{lang.id}/interpreter"
        # A package interpreter is its directory.
        assert found[0] in {f"{interpreter}.py", interpreter}, name
        generator = Path(inspect.getfile(lang.boolean))
        if generator.name == "__init__.py":
            generator = generator.parent
        assert found[1] == generator.relative_to(new_language.ROOT).as_posix(), name
