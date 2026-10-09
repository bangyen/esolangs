"""Tests for the new-language scaffolder."""

import sys
from pathlib import Path

import pytest

from scripts import new_language, remove_language


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    template = tmp_path / "src/esolangs/interpreters/_template.py"
    template.parent.mkdir(parents=True)
    template.write_text('"""Template for a new esolang interpreter.\n"""\n')
    monkeypatch.setattr(new_language, "ROOT", tmp_path)
    return tmp_path


@pytest.mark.usefixtures("root")
def test_scaffold_creates_source_generator_and_tests() -> None:
    source, test, generator, generator_test = new_language.scaffold(
        "Tiny Lang", "other"
    )
    assert source.name == generator.name == "tiny_lang.py"
    assert (test.name, generator_test.name) == (
        "test_tiny_lang.py",
        "test_boolean_tiny_lang.py",
    )
    assert "Interpreter for Tiny Lang." in source.read_text()
    assert "def tiny_lang(truth_table: str) -> str:" in generator.read_text()


@pytest.mark.usefixtures("root")
def test_an_interpreter_only_language_gets_no_generator() -> None:
    paths = new_language.scaffold("Tiny", "other", generator=False)
    assert [path.name for path in paths] == ["tiny.py", "test_tiny.py"]


def test_scaffold_records_the_language_as_unassessed(root: Path) -> None:
    curation = root / "tests/fixtures/curation.toml"
    curation.parent.mkdir(parents=True)
    curation.write_text('[languages]\nKept = { route = "fame" }\n')
    new_language.scaffold("Tiny Lang", "other", generator=False)
    assert curation.read_text().endswith('"Tiny Lang" = { route = "unassessed" }\n')


def test_scaffold_refuses_overwrite(root: Path) -> None:
    target = root / "src/esolangs/interpreters/other/tiny.py"
    target.parent.mkdir(parents=True)
    target.write_text("owned")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        new_language.scaffold("Tiny", "other")


def test_the_slug_is_the_registry_id() -> None:
    """A second slug rule refused ``123`` and gave Piet++ Piet's file."""
    from esolangs.registry import LANGUAGES

    for name, lang in LANGUAGES.items():
        assert new_language._slug(name) == lang.id, name  # noqa: SLF001
    with pytest.raises(ValueError, match="keyword"):
        new_language._slug("class")  # noqa: SLF001


def test_remove_cuts_only_entries_that_own_their_lines(tmp_path: Path) -> None:
    path = tmp_path / "table.py"
    path.write_text(
        "from esolangs.tools.gone import gone\n"
        "from esolangs.tools.gone import PAIR\n"
        'T = {\n    "kept": PAIR,\n    # gone\'s note\n    "gone": 1,\n}\n'
        'L = ["gone", "kept"]\n'
        'run_gone = _runner("gone")\n'
    )
    modules = {"esolangs.tools.gone"}
    assert remove_language._drop_entries(path, {"gone"}, modules) == 3  # noqa: SLF001
    # The import another entry still uses stays.
    assert path.read_text() == (
        "from esolangs.tools.gone import PAIR\n"
        'T = {\n    "kept": PAIR,\n}\nL = ["gone", "kept"]\n'
    )


def test_remove_drops_the_whole_limitations_bullet(tmp_path: Path) -> None:
    path = tmp_path / "limitations.md"
    path.write_text("- Gone reads\n  past EOF.\n- Gonero stays.\n  Kept.\n")
    remove_language._drop_bullets(path, "Gone")  # noqa: SLF001
    assert path.read_text() == "- Gonero stays.\n  Kept.\n"


def test_check_flags_a_leftover_placeholder_test(root: Path) -> None:
    new_language.scaffold("Tiny", "other", generator=False)
    fixtures = root / "tests/fixtures"
    fixtures.mkdir()
    (fixtures / "curation.toml").write_text("[languages]\n")
    gaps = new_language._common_gaps("Tiny", "other.tiny")  # noqa: SLF001
    assert ("tests/interpreters/test_tiny.py", "replace the placeholder test") in {
        (gap.where, gap.fix) for gap in gaps
    }


def test_finish_still_runs_the_gate_past_open_steps(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fixtures = root / "tests/fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "curation.toml").write_text(
        '[languages]\nTiny = { route = "unassessed" }\n'
    )
    gap = new_language.Gap("somewhere", "do it")
    monkeypatch.setattr(new_language, "check", lambda _: [gap])
    ran = []
    monkeypatch.setattr(new_language, "_gate", lambda: ran.append(1) or 0)
    assert new_language.finish("Tiny") == 1
    assert ran == [1]
    assert "curation unassessed" in capsys.readouterr().out


def test_check_with_open_steps_is_not_a_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import types

    fake = types.ModuleType("generate_exports")
    fake.update = lambda *_: None  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "generate_exports", fake)
    gap = new_language.Gap("somewhere", "do it")
    monkeypatch.setattr(new_language, "check", lambda _: [gap])
    assert new_language.main(["check", "Tiny"]) == 0
    assert "1 step(s) left" in capsys.readouterr().out


@pytest.mark.usefixtures("root")
@pytest.mark.parametrize("interpreter_only", [False, True])
def test_start_prints_the_matching_contributor_workflow(
    *, interpreter_only: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ["start", "Tiny Lang", "--category", new_language.CATEGORIES[0]]
    if interpreter_only:
        args.append("--interpreter-only")
    assert new_language.main(args) == 0
    output = capsys.readouterr().out
    next_step = next(line for line in output.splitlines() if line.startswith("next:"))
    assert ("generator" in next_step) is not interpreter_only
    assert "then: just check-language 'Tiny Lang'" in output


def test_gap_report_prints_a_shell_safe_followup(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import shlex

    name = "Tiny's $Lang"
    new_language._report(  # noqa: SLF001
        name, [new_language.Gap("source", "implement the interpreter")]
    )
    command = capsys.readouterr().out.split("after fixing these: ")[1].strip()
    assert shlex.split(command) == ["just", "check-language", name]
