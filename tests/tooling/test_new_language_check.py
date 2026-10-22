"""``new_language.py check`` agrees with the suite on every registered language."""

import dataclasses
import importlib
import inspect
import io
import subprocess
import tomllib
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


def test_an_unassessed_language_does_not_break_the_census(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``start`` scaffolds ``unassessed``; the docs step raised KeyError on it."""
    generate = importlib.import_module("docs.generate")  # beside new_language
    rows = {"A": {"backlinks": 60}, "B": {"backlinks": 3}, "C": {"unassessed": True}}
    monkeypatch.setattr(generate, "_curation_rows", lambda: rows)
    text = generate.render_curation_census_section()
    assert "1 clear the fame gate" in text
    assert "1 are first implementations" in text
    assert "1 more await" in text


def test_a_failed_regeneration_ends_check_in_one_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(new_language, "check", lambda _: [])
    monkeypatch.setattr(new_language, "_dirty", set)
    monkeypatch.setattr(
        new_language.subprocess,
        "run",
        lambda cmd, **_: subprocess.CompletedProcess(cmd, 1),
    )
    assert new_language.main(["check", _LONGEST]) == 1
    out = capsys.readouterr().out
    assert "rerun: python scripts/docs/generate.py examples" in out


def test_start_on_a_terminal_asks_for_the_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    made = _scaffolded(monkeypatch)
    monkeypatch.setattr("sys.stdin", _Terminal("tape_based\n"))
    assert new_language.main(["start", "Not A Language"]) == 0
    assert made == ["tape_based"]


@pytest.mark.parametrize(
    ("values", "cell"),
    [
        ([15, 20, 25], "poly n: worst 5n commands"),
        ([4, 5, 6], "poly n: worst n + 1 commands"),
        ([7, 7, 7], "poly n: worst 7 commands"),
        ([1, 4, 7], "poly n: worst 3n - 8 commands"),
        ([10, 15], "FILL: at most <formula in n, T, L> commands"),
        ([10, 15, 21], "FILL: at most <formula in n, T, L> commands"),
    ],
)
def test_bounds_fits_a_line_through_three_arities(values: list[int], cell: str) -> None:
    # n = 1 and 2 sit off the line: the formula tests start at n = 3.
    rows = [(1, 999), (2, 0), *zip(range(3, 6), values, strict=False)]
    assert new_language._fit(rows, "commands") == cell  # noqa: SLF001


def _measured(monkeypatch: pytest.MonkeyPatch, *, ledger: bool) -> None:
    rows, other = new_language._proof_status_load()  # noqa: SLF001
    if not ledger:
        rows = [row for row in rows if row.generator != _LONGEST]
    monkeypatch.setattr(new_language, "_proof_status_load", lambda: (rows, other))
    monkeypatch.setattr(
        new_language,
        "bounds",
        lambda _, ns: [(n, 5 * n + 28, n * n, 2, "01", "10") for n in ns],
    )
    assert new_language.main(["bounds", _LONGEST]) == 0


def test_bounds_drafts_a_section_that_parses(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _measured(monkeypatch, ledger=False)
    out = capsys.readouterr().out
    section = tomllib.loads(out[out.index("[proof_status]") :])["proof_status"]
    assert section["execution"] == "poly n: worst 5n + 28 commands"
    # n * n is no line: left for the author.
    assert section["workspace"].startswith("FILL")
    assert "tree" in section["labels"][0]


def test_bounds_on_a_ledger_row_prints_only_what_it_fits(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _measured(monkeypatch, ledger=True)
    out = capsys.readouterr().out
    assert "[proof_status]" not in out
    assert "FILL" not in out
    assert 'execution = "poly n: worst 5n + 28 commands"' in out


def test_bounds_on_a_stub_says_to_implement_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def stub(*_: object) -> None:
        raise NotImplementedError

    monkeypatch.setattr(new_language, "bounds", stub)
    assert new_language.main(["bounds", _LONGEST]) == 1
    assert "implement the generator first" in capsys.readouterr().err


def test_a_pasted_section_with_fill_left_is_a_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows, other = new_language._proof_status_load()  # noqa: SLF001
    row = next(row for row in rows if row.generator == _LONGEST)
    rows = [
        dataclasses.replace(row, scaling="FILL: linear") if r is row else r
        for r in rows
    ]
    monkeypatch.setattr(new_language, "_proof_status_load", lambda: (rows, other))
    (gap,) = new_language._ledger_gaps(_LONGEST)  # noqa: SLF001
    assert gap.fix == "replace each FILL in [proof_status]"


def test_quick_tests_spell_ids_as_pytest_does() -> None:
    """Pytest escapes ``þ``; an unescaped id was "not found" and aborted check."""
    name = next(name for name in LANGUAGES if not name.isascii())
    ids = new_language.quick_tests(name)
    assert all(node.isascii() for node in ids)
    assert any(name.encode("unicode_escape").decode() in node for node in ids)


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
