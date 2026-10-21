"""``new_language.py check`` agrees with the suite on every registered language."""

import inspect
import io
from pathlib import Path

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from scripts import new_language
from tests.support import samples
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


class _Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


def _scaffolded(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    made: list[str] = []
    monkeypatch.setattr(
        new_language, "scaffold", lambda _, c, **__: made.append(c) or []
    )
    return made


def test_start_without_a_category_lists_them(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    made = _scaffolded(monkeypatch)
    with pytest.raises(SystemExit):
        new_language.main(["start", "Not A Language"])
    err = capsys.readouterr().err
    assert all(category in err for category in new_language.CATEGORIES)
    assert not made


def test_start_on_a_terminal_asks_for_the_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    made = _scaffolded(monkeypatch)
    monkeypatch.setattr("sys.stdin", _Terminal("tape_based\n"))
    assert new_language.main(["start", "Not A Language"]) == 0
    assert made == ["tape_based"]


def test_a_generator_language_needs_no_hand_sample() -> None:
    # samples is imported above, like every other user: imported here, its
    # one-off cost (a fresh venv's first PIL load, 0.95 s of 2.89 s cold)
    # was charged to this 1 s fast-band test, which then failed once per
    # new worktree.
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
