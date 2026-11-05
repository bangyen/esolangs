"""``new_language.py check`` agrees with the suite on every registered language."""

import dataclasses
import importlib
import inspect
import subprocess
from pathlib import Path

import pytest

import esolangs
from esolangs import compat
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
    assert gap.where == "src/esolangs/languages/not_a_language/descriptor.py"
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
    registered = new_language._registered_name
    assert registered(_LONGEST.swapcase()) == _LONGEST
    assert registered("Not A Language") == "Not A Language"


def _scaffolded(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    made: list[str] = []
    monkeypatch.setattr(
        new_language, "scaffold", lambda _, c, **__: made.append(c) or []
    )
    return made


def test_start_requires_a_category(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    made = _scaffolded(monkeypatch)
    with pytest.raises(SystemExit):
        new_language.main(["start", "Not A Language"])
    err = capsys.readouterr().err
    assert "--category" in err
    assert "required" in err
    assert not made


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


def test_bounds_reports_measurements_and_witnesses(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        new_language,
        "bounds",
        lambda _, ns: [(n, 5 * n + 28, 3**n, 2, "01", "10") for n in ns],
    )
    monkeypatch.setattr(new_language, "size_anchors", lambda _: ["anchor control"])
    assert new_language.main(["bounds", _LONGEST]) == 0
    out = capsys.readouterr().out
    assert "witness tables (steps, bits)" in out
    for n in range(1, 7):
        assert f"{n:<2} {5 * n + 28:>9}  {3**n:>9}  {2:>9}  01 10" in out
    assert "anchor control" in out
    assert "[proof_status]" not in out
    assert "execution =" not in out


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
    rows, other = new_language._proof_status_load()
    row = next(row for row in rows if row.generator == _LONGEST)
    rows = [
        dataclasses.replace(row, qualification="FILL") if r is row else r for r in rows
    ]
    monkeypatch.setattr(new_language, "_proof_status_load", lambda: (rows, other))
    (gap,) = new_language._ledger_gaps(_LONGEST)
    assert gap.fix == "replace each FILL in [proof_status]"


def test_quick_tests_spell_ids_as_pytest_does() -> None:
    """Pytest escapes ``þ``; an unescaped id was "not found" and aborted check."""
    name = next(name for name in LANGUAGES if not name.isascii())
    ids = new_language.quick_tests(name)
    assert all(node.isascii() for node in ids)
    assert any(name.encode("unicode_escape").decode() in node for node in ids)


def test_bounds_flags_a_stale_size_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: an anchor one char off is named with the real size."""
    name = first(boolean_generator=True, parameterized=False, answer_mode="output")
    from docs import evidence

    size = len(str(compat.generate(name, "0110")))
    anchor = dataclasses.replace(
        evidence.source_anchors(name)[0],
        witness=evidence.TableWitness(2, "parity"),
        size=size + 1,
        unit="chars",
    )
    monkeypatch.setattr(evidence, "source_anchors", lambda _: (anchor,))
    assert new_language.size_anchors(name) == [
        f"  n=2 parity: {size + 1:,} chars  STALE: emits {size:,}"
    ]
    load_module = importlib.import_module

    def without_formula_records(module, *args, **kwargs):
        assert module != "tests.proofs.execution", "measurement loaded its own claims"
        return load_module(module, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", without_formula_records)
    assert len(new_language.bounds(name, range(1, 2))) == 1

    def absent(_name):
        raise KeyError("evidence")

    monkeypatch.setattr(evidence, "source_anchors", absent)
    assert new_language.size_anchors(name) == []


def test_a_generator_language_needs_no_hand_sample() -> None:
    # samples is imported above, like every other user: imported here, its
    # one-off cost (a fresh venv's first PIL load, 0.95 s of 2.89 s cold)
    # was charged to this 1 s fast-band test, which then failed once per
    # new worktree.
    name = first(boolean_generator=True, parameterized=False, answer_mode="output")
    program, stdin = samples._generated(name)
    assert esolangs.read_answer(name, compat.run(name, program, stdin=stdin)) == "1"


def test_sources_names_the_interpreter_and_generator() -> None:
    for name, lang in LANGUAGES.items():
        if lang.runtime.interpreter is None or lang.backend is None:
            continue
        found = new_language.sources(name)
        interpreter = f"src/esolangs/languages/{lang.id}/interpreter"
        # A package interpreter is its directory.
        assert found[0] in {f"{interpreter}.py", interpreter}, name
        generator = Path(inspect.getfile(lang.backend.generate))
        if generator.name == "__init__.py":
            generator = generator.parent
        assert found[1] == generator.relative_to(new_language.ROOT).as_posix(), name
