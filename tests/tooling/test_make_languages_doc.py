"""Generated README and usage sections stay in sync with the registry."""

import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tests.support.pick import one
from tests.support.reference import REFERENCE
from tests.tooling.script_support import load

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "docs" / "generate.py"
README = REPO_ROOT / "README.md"
USAGE_DOC = REPO_ROOT / "docs" / "usage.md"
LIMITATIONS = REPO_ROOT / "docs" / "limitations.md"
CONTRIBUTING = REPO_ROOT / "docs" / "CONTRIBUTING.md"
LANGUAGE_REQUEST = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "language_request.yml"


def _markers(tag: str) -> tuple[str, str]:
    """Return the pair of HTML comments the generator fences ``tag`` with."""
    return f"<!-- {tag}:START -->", f"<!-- {tag}:END -->"


_README_START, _README_END = _markers("IMPLEMENTED")
_EXAMPLES_START, _EXAMPLES_END = _markers("EXAMPLES")
_BOOLEAN_COUNT_START, _BOOLEAN_COUNT_END = _markers("BOOLEAN-COUNT")
_SHAPES_START, _SHAPES_END = _markers("INPUT-SHAPES")
_API_START, _API_END = _markers("PUBLIC-API")


def load_script() -> Any:
    return load(SCRIPT)


def test_readme_counts_match_the_registry() -> None:
    """The rendered counts are the registry's, not a hand-typed number."""
    module = load_script()
    examples = module.render_examples_section()
    count = sum(lang.boolean is not None for lang in module.LANGUAGES.values())
    assert f"each of the {count}\nlanguages with a boolean" in examples
    assert f"  {len(module.BOOLEAN)} of the" in module.render_boolean_count_section()


def test_contributor_facts_match_the_registry() -> None:
    """The generator home is validated and the language count is generated."""
    module = load_script()
    assert module.render_contributor_tools_section() in CONTRIBUTING.read_text()
    module.update_contributing()
    assert (
        f"What it adds that the current {len(module.LANGUAGES)} do not"
        in LANGUAGE_REQUEST.read_text()
    )


def test_a_generator_outside_tools_is_rejected() -> None:
    """The contributor path must describe every registry generator."""
    module = load_script()

    def elsewhere() -> str:
        return ""

    language = next(iter(module.LANGUAGES.values()))
    module.LANGUAGES = {language.name: replace(language, boolean=elsewhere)}
    with pytest.raises(ValueError, match="generator is outside"):
        module.render_contributor_tools_section()


def test_a_language_without_a_generator_is_ignored() -> None:
    """Only registry entries that claim a generator constrain its home."""
    module = load_script()
    language = next(iter(module.LANGUAGES.values()))
    module.LANGUAGES = {language.name: replace(language, boolean=None)}
    assert module.render_contributor_tools_section().endswith(
        "| shared generator helpers |"
    )


def test_an_incorrect_contributor_path_is_rejected(tmp_path: Path) -> None:
    module = load_script()
    path = tmp_path / "docs" / "CONTRIBUTING.md"
    path.parent.mkdir()
    path.write_text("| `src/esolangs/generation/boolean/` | generators |\n")
    module.render_contributor_tools_section = lambda: "correct row"
    with pytest.raises(ValueError, match="does not name"):
        module.update_contributing(tmp_path)


def test_the_issue_template_must_contain_one_count(tmp_path: Path) -> None:
    """A wording change cannot silently disable count generation."""
    module = load_script()
    path = tmp_path / ".github" / "ISSUE_TEMPLATE" / "language_request.yml"
    path.parent.mkdir(parents=True)
    path.write_text("no generated count here\n")
    with pytest.raises(ValueError, match="expected one language count"):
        module.update_language_request(tmp_path)


def test_the_issue_template_count_is_rewritten(tmp_path: Path) -> None:
    module = load_script()
    path = tmp_path / ".github" / "ISSUE_TEMPLATE" / "language_request.yml"
    path.parent.mkdir(parents=True)
    path.write_text("What it adds that the current 1 do not — enough\n")
    module.update_language_request(tmp_path)
    assert f"current {len(module.LANGUAGES)} do not" in path.read_text()


def test_main_updates_all_registry_derived_docs(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """The public generator command includes both contributor surfaces."""
    module = load_script()
    called = []
    # The stubs report a change, as a stale artifact would: docs_main only
    # prints an "updated ..." line for an artifact that actually changed.
    module.update_readme = lambda _root: called.append("readme") or True
    module.update_usage = lambda _root: called.append("usage") or True
    module.update_limitations = lambda _root: called.append("limitations") or True
    module.update_contributing = lambda _root: called.append("contributing")
    module.update_language_request = lambda _root: called.append("request") or True
    for relative in (
        "docs/proofs/index.md",
        "docs/roadmap.md",
        "src/esolangs/languages/generators.py",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO_ROOT / relative).read_bytes())
    status = module.docs_main(output_root=tmp_path)
    out = capsys.readouterr().out
    stale = f"docs are stale; run uv run python scripts/docs/generate.py docs\n{out}"
    assert status == 0, stale
    assert called == ["readme", "usage", "limitations", "contributing", "request"]
    assert "language request template" in out
    # The real exports and proof tables were copied in sync, so they earn
    # no "updated" line -- only the summary counts them.
    assert "updated the generated exports" not in out, stale
    assert "updated the generated tables of docs/proofs" not in out, stale
    assert "updated the audit progress of docs/roadmap.md" not in out, stale
    assert "3 generated artifacts already up to date" in out


def test_the_writers_rewrite_the_committed_sections(tmp_path: Path) -> None:
    """The ``update_*`` writers splice the marked blocks, as generate.py does."""
    module = load_script()
    (tmp_path / "docs").mkdir()
    readme = README.read_text()
    usage = USAGE_DOC.read_text()
    limitations = LIMITATIONS.read_text()
    (tmp_path / "README.md").write_text(readme)
    (tmp_path / "docs" / "usage.md").write_text(usage)
    (tmp_path / "docs" / "limitations.md").write_text(limitations)
    catalog = REPO_ROOT / "docs" / "languages.md"
    (tmp_path / "docs" / "languages.md").write_text(catalog.read_text())
    # In-sync copies are not rewritten, and the writers say so.
    assert module.update_readme(tmp_path) is False
    assert (tmp_path / "docs" / "languages.md").read_text() == catalog.read_text()
    assert module.update_usage(tmp_path) is False
    assert module.update_limitations(tmp_path) is False
    assert (tmp_path / "README.md").read_text() == readme
    assert (tmp_path / "docs" / "usage.md").read_text() == usage
    assert (tmp_path / "docs" / "limitations.md").read_text() == limitations


def test_a_stale_section_is_rewritten_and_reports_a_change(tmp_path: Path) -> None:
    """A stale writer changes the file once, then reports it up to date."""
    module = load_script()
    (tmp_path / "docs").mkdir()
    readme = README.read_text()
    start, end = _markers("PACKAGE-COUNT")
    stale = readme.replace(_marked(readme, start, end), start + "\nstale\n" + end)
    (tmp_path / "README.md").write_text(stale)
    catalog = REPO_ROOT / "docs" / "languages.md"
    (tmp_path / "docs" / "languages.md").write_text(catalog.read_text())
    assert module.update_readme(tmp_path) is True
    assert (tmp_path / "README.md").read_text() == readme
    assert module.update_readme(tmp_path) is False


def test_an_unheaded_category_names_where_to_add_it() -> None:
    """A new category fails with the fix, not a ``KeyError``."""
    module = load_script()
    language = next(
        lang for lang in module.LANGUAGES.values() if lang.interpreter is not None
    )
    module.LANGUAGES = {language.name: replace(language, category="new_category")}
    with pytest.raises(ValueError, match="_README_HEADINGS"):
        module.render_languages_section()


def _marked(text: str, start: str, end: str) -> str:
    return text[text.index(start) : text.index(end) + len(end)]


def test_the_shape_table_carries_the_encoders_output() -> None:
    """A wrong-but-in-sync table cannot pass the sync test above."""
    module = load_script()
    rendered = module.render_input_shapes_section()
    # Row 5 is 101; a padded stream leads an odd count with a zero.
    for name in one(input_shape="row_index"):
        assert f"| {name} | `row_index` | `0`/`1` | `'5\\n'` |" in rendered


def test_boolean_set_names_are_registered() -> None:
    """Every language marked boolean in the matrix is a registered language."""
    module = load_script()
    assert set(module.LANGUAGES) >= module.BOOLEAN


def test_language_listing_covers_every_interpreter() -> None:
    module = load_script()
    rendered = module.render_languages_section()
    for name, language in module.LANGUAGES.items():
        if language.interpreter is not None:
            assert f"- [{name}]" in rendered
    for path in re.findall(r"/blob/main/([^)]*)", rendered):
        assert (REPO_ROOT / path).is_file()


def test_language_listing_only_lists_available_interpreters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script()
    monkeypatch.setitem(
        module.LANGUAGES,
        REFERENCE,
        replace(module.LANGUAGES[REFERENCE], interpreter=None),
    )
    rendered = module.render_languages_section()
    assert f"- [{REFERENCE}]" not in rendered
    assert rendered.count("- [") == len(module.LANGUAGES) - 1


# Standalone coverage run: 2.64s exceeds the fast band.
@pytest.mark.medium
@pytest.mark.parametrize("stale", [False, True])
def test_documentation_check_preserves_source_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *,
    stale: bool,
) -> None:
    from checks import check_docs

    for relative in check_docs.GENERATED:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO_ROOT / relative).read_bytes())
    readme = tmp_path / "README.md"
    if stale:
        text = readme.read_text()
        start, end = _markers("PACKAGE-COUNT")
        readme.write_text(
            text.replace(_marked(text, start, end), start + "\nstale\n" + end)
        )
    before = {
        relative: (
            (tmp_path / relative).read_bytes(),
            (tmp_path / relative).stat().st_mtime_ns,
        )
        for relative in check_docs.GENERATED
    }
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    assert check_docs.stale_generated() == int(stale)
    assert {
        relative: (
            (tmp_path / relative).read_bytes(),
            (tmp_path / relative).stat().st_mtime_ns,
        )
        for relative in check_docs.GENERATED
    } == before
    error = capsys.readouterr().err
    assert ("run python scripts/docs/generate.py docs: README.md" in error) == stale


def test_missing_canonical_interpreter_does_not_link_to_an_old_path(tmp_path) -> None:
    module = load_script()
    module.ROOT = tmp_path
    language = next(iter(module.LANGUAGES.values()))
    old = tmp_path / "src/esolangs/runtime" / f"{language.interpreter}.py"
    old.parent.mkdir(parents=True)
    old.write_text("owned")
    with pytest.raises(FileNotFoundError, match="no canonical interpreter"):
        module._source_link(language.name)  # noqa: SLF001


def test_exports_use_the_canonical_generator_module(tmp_path) -> None:
    from scripts.docs.generate import declared

    tools = tmp_path / "src/esolangs/generation"
    tools.mkdir(parents=True)
    (tools / "different.py").write_text(
        "if TYPE_CHECKING:\n"
        "    from esolangs.languages.fixture.generator import fixture as fixture\n"
    )
    package = tmp_path / "src/esolangs/languages/fixture"
    package.mkdir(parents=True)
    (package / "generator.py").write_text(
        "def fixture(table): return table\n"
        "LANGUAGE = Language('Fixture', boolean=fixture)\n"
    )
    assert declared(tmp_path) == [("esolangs.languages.fixture.generator", "fixture")]


def test_discovery_ignores_noncanonical_declarations(tmp_path) -> None:
    from scripts.docs.generate import declared

    language = tmp_path / "src/esolangs/languages/fixture"
    package = language / "generator"
    package.mkdir(parents=True)
    source = "LANGUAGE = Language('Fixture', boolean=fixture)\n"
    (package / "__init__.py").write_text(source)
    (package / "helper.py").write_text(source)
    (language / "interpreter.py").write_text(source)
    assert declared(tmp_path) == [("esolangs.languages.fixture.generator", "fixture")]
