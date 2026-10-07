"""Generated README and usage sections stay in sync with the registry."""

import importlib.util
import re
from dataclasses import replace
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "generate_docs.py"
README = REPO_ROOT / "README.md"
USAGE_DOC = REPO_ROOT / "docs" / "usage.md"
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
_TUI_START, _TUI_END = _markers("TUI-FRAME")


def load_script() -> object:
    spec = importlib.util.spec_from_file_location("make_languages_doc", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


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
    assert module.render_contributor_tools_section().endswith("| generators |")


def test_an_incorrect_contributor_path_is_rejected(tmp_path: Path) -> None:
    module = load_script()
    module.ROOT = tmp_path
    path = tmp_path / "docs" / "CONTRIBUTING.md"
    path.parent.mkdir()
    path.write_text("| `src/esolangs/tools/boolean/` | generators |\n")
    module.render_contributor_tools_section = lambda: "correct row"
    with pytest.raises(ValueError, match="does not name"):
        module.update_contributing()


def test_the_issue_template_must_contain_one_count(tmp_path: Path) -> None:
    """A wording change cannot silently disable count generation."""
    module = load_script()
    module.ROOT = tmp_path
    path = tmp_path / ".github" / "ISSUE_TEMPLATE" / "language_request.yml"
    path.parent.mkdir(parents=True)
    path.write_text("no generated count here\n")
    with pytest.raises(ValueError, match="expected one language count"):
        module.update_language_request()


def test_the_issue_template_count_is_rewritten(tmp_path: Path) -> None:
    module = load_script()
    module.ROOT = tmp_path
    path = tmp_path / ".github" / "ISSUE_TEMPLATE" / "language_request.yml"
    path.parent.mkdir(parents=True)
    path.write_text("What it adds that the current 1 do not — enough\n")
    module.update_language_request()
    assert f"current {len(module.LANGUAGES)} do not" in path.read_text()


def test_main_updates_all_registry_derived_docs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The public generator command includes both contributor surfaces."""
    module = load_script()
    called = []
    module.update_readme = lambda: called.append("readme")
    module.update_usage = lambda: called.append("usage")
    module.update_contributing = lambda: called.append("contributing")
    module.update_language_request = lambda: called.append("request")
    assert module.main() == 0
    assert called == ["readme", "usage", "contributing", "request"]
    assert "language request template" in capsys.readouterr().out


def test_the_writers_rewrite_the_committed_sections(tmp_path: Path) -> None:
    """The ``update_*`` writers splice the marked blocks, as generate.py does."""
    module = load_script()
    (tmp_path / "docs").mkdir()
    readme = README.read_text()
    usage = USAGE_DOC.read_text()
    (tmp_path / "README.md").write_text(readme)
    (tmp_path / "docs" / "usage.md").write_text(usage)
    module.ROOT = tmp_path
    module.update_readme()
    module.update_usage()
    assert (tmp_path / "README.md").read_text() == readme
    assert (tmp_path / "docs" / "usage.md").read_text() == usage


def test_the_tui_frame_has_no_trailing_whitespace() -> None:
    """`trailing-whitespace` runs on README.md and would strip the padding."""
    module = load_script()
    rendered = module.render_tui_section()
    assert not [line for line in rendered.splitlines() if line != line.rstrip()]


def test_the_tui_frame_draws_the_generators_own_program() -> None:
    """Not a mock-up: each drawn row is a row of the generated program."""
    module = load_script()
    import esolangs

    program = esolangs.generate("Flowchart", "0110")
    rows = program.splitlines()
    drawn = [
        line.split("|", 1)
        for line in module.render_tui_section().splitlines()
        if re.fullmatch(r"\s*\d+ \|.*", line)
    ]
    assert drawn, "no numbered program rows on the screen"
    for number, body in drawn:
        # The pane is windowed by column, so the drawn text is a slice of
        # the row it is numbered with -- one-based, as the screen shows it.
        assert body.strip() in rows[int(number) - 1], (number, body)


def _marked(text: str, start: str, end: str) -> str:
    return text[text.index(start) : text.index(end) + len(end)]


def test_the_shape_table_carries_the_encoders_output() -> None:
    """A wrong-but-in-sync table cannot pass the sync test above."""
    module = load_script()
    rendered = module.render_input_shapes_section()
    assert "| Fargo | `row_index` | `0`/`1` | `'5\\n'` |" in rendered
    assert "| Taglate | `char_stream_padded` | `0`/`1` | `'0101'` |" in (rendered)


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
        module.LANGUAGES, "Line", replace(module.LANGUAGES["Line"], interpreter=None)
    )
    rendered = module.render_languages_section()
    assert "- [Line]" not in rendered
    assert f"Show all {len(module.LANGUAGES) - 1} languages" in rendered
