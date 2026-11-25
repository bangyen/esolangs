"""Generated README and usage sections stay in sync with the registry."""

import re
from dataclasses import replace
from functools import partial
from pathlib import Path

import pytest

from scripts.docs.writing import GENERATED_DOCS
from tests.support.pick import one
from tests.support.reference import REFERENCE
from tests.tooling.script_support import load

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "docs" / "generate.py"
README = REPO_ROOT / "README.md"
USAGE_DOC = REPO_ROOT / "docs" / "usage.md"
LIMITATIONS = REPO_ROOT / "docs" / "limitations.md"


def _markers(tag: str) -> tuple[str, str]:
    """Return the pair of HTML comments the generator fences ``tag`` with."""
    return f"<!-- {tag}:START -->", f"<!-- {tag}:END -->"


_README_START, _README_END = _markers("IMPLEMENTED")
_EXAMPLES_START, _EXAMPLES_END = _markers("EXAMPLES")
_BOOLEAN_COUNT_START, _BOOLEAN_COUNT_END = _markers("BOOLEAN-COUNT")
_SHAPES_START, _SHAPES_END = _markers("INPUT-SHAPES")
_API_START, _API_END = _markers("PUBLIC-API")


load_script = partial(load, SCRIPT)


def test_readme_counts_match_the_registry() -> None:
    """The rendered counts are the registry's, not a hand-typed number."""
    module = load_script()
    examples = module.render_examples_section()
    count = sum(lang.backend is not None for lang in module.LANGUAGES.values())
    assert f"each of the {count}\nlanguages with a boolean" in examples
    assert f"  {count} of the" in module.render_boolean_count_section()


def test_generators_live_in_their_language_packages() -> None:
    module = load_script()
    for language in module.LANGUAGES.values():
        if language.backend is None:
            continue
        source = Path(language.backend.generate.__code__.co_filename).resolve()
        home = REPO_ROOT / "src/esolangs/languages" / language.id / "generator"
        assert (
            source.is_relative_to(home.resolve())
            or source == home.with_suffix(".py").resolve()
        ), language.name


def test_main_updates_all_registry_derived_docs(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """The public generator command updates each generated document."""
    module = load_script()
    called = []
    # The stubs report a change, as a stale artifact would: docs_main only
    # prints an "updated ..." line for an artifact that actually changed.
    module.update_readme = lambda _root: called.append("readme") or True
    module.update_usage = lambda _root: called.append("usage") or True
    module.update_limitations = lambda _root: called.append("limitations") or True
    for relative in GENERATED_DOCS:
        if relative == "src/esolangs/registry/well_known.json":
            continue
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO_ROOT / relative).read_bytes())
    status = module.docs_main(output_root=tmp_path)
    out = capsys.readouterr().out
    stale = f"docs are stale; run uv run python scripts/docs/generate.py docs\n{out}"
    assert status == 0, stale
    assert called == ["readme", "usage", "limitations"]
    # The real proof tables and scaling catalogue were copied in sync, so they earn
    # no "updated" line -- only the summary counts them.
    assert "updated the generated tables of docs/proofs" not in out, stale
    assert "2 generated artifacts already up to date" in out


@pytest.mark.parametrize("side", ["START", "END"])
def test_failed_docs_render_preserves_all_published_files(tmp_path, capsys, side):
    module = load_script()
    for relative in GENERATED_DOCS:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO_ROOT / relative).read_bytes())
    proof = tmp_path / "docs/proofs/index.md"
    marker = "<!-- PROOF-TOTALS:START -->"
    proof.write_text(proof.read_text().replace(marker, marker + "\nold proof table"))
    usage = tmp_path / "docs/usage.md"
    missing = f"<!-- PUBLIC-API:{side} -->"
    usage.write_text(usage.read_text().replace(missing, ""))
    before = {name: (tmp_path / name).read_bytes() for name in GENERATED_DOCS}

    with pytest.raises(
        ValueError, match=f"docs/usage.md: missing generated marker {missing}"
    ):
        module.docs_main(output_root=tmp_path)

    assert {name: (tmp_path / name).read_bytes() for name in before} == before
    assert not list(tmp_path.glob(".docs-render-*"))
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("restore_failure", [False, True])
def test_failed_docs_publication_restores_originals(
    tmp_path, monkeypatch, capsys, restore_failure
):
    module = load_script()
    new_path = "src/esolangs/registry/well_known.json"
    for name in GENERATED_DOCS:
        if name != new_path:
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((REPO_ROOT / name).read_bytes())
    proof = tmp_path / "docs/proofs/index.md"
    usage = tmp_path / "docs/usage.md"
    for path, marker in (
        (proof, "<!-- PROOF-TOTALS:START -->"),
        (usage, "<!-- INPUT-SHAPES:START -->"),
    ):
        path.write_text(
            path.read_text().replace(marker, marker + "\nold generated text")
        )
    before = {
        tmp_path / name: (tmp_path / name).read_bytes()
        for name in GENERATED_DOCS
        if name != new_path
    }
    replace = Path.replace

    def refuse(path, target):
        if target == usage:
            raise OSError("injected publication failure")
        if restore_failure and target == proof and ".docs-publish" in path.parts:
            raise OSError("injected restoration failure")
        return replace(path, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", refuse)
        with pytest.raises(OSError, match="injected publication failure") as caught:
            module.docs_main(output_root=tmp_path)

    backup = tmp_path / ".docs-publish/docs/proofs/index.md"
    if restore_failure:
        assert "injected restoration failure" in str(caught.value)
        assert str(backup.parents[2]) in str(caught.value)
        assert backup.read_bytes() == before[proof]
        backup.replace(proof)
    else:
        assert not (tmp_path / ".docs-publish").exists()
    assert all(path.read_bytes() == original for path, original in before.items())
    assert not (tmp_path / new_path).exists()
    assert not list(tmp_path.glob(".docs-render-*"))
    assert capsys.readouterr().out == ""


@pytest.mark.usefixtures("retired_source_adapters")
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
        lang
        for lang in module.LANGUAGES.values()
        if lang.runtime.interpreter is not None
    )
    module.LANGUAGES = {
        language.name: replace(
            language, runtime=replace(language.runtime, category="new_category")
        )
    }
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


def test_language_listing_covers_every_interpreter() -> None:
    module = load_script()
    rendered = module.render_languages_section()
    for name, language in module.LANGUAGES.items():
        if language.runtime.interpreter is not None:
            assert f"- [{name}]" in rendered
    for path in re.findall(r"/blob/main/([^)]*)", rendered):
        assert (REPO_ROOT / path).is_file()


def test_language_listing_only_lists_available_interpreters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script()
    changed = replace(
        module.LANGUAGES[REFERENCE],
        runtime=replace(module.LANGUAGES[REFERENCE].runtime, interpreter=None),
    )
    monkeypatch.setattr(module, "LANGUAGES", {**module.LANGUAGES, REFERENCE: changed})
    rendered = module.render_languages_section()
    assert f"- [{REFERENCE}]" not in rendered
    assert rendered.count("- [") == len(module.LANGUAGES) - 1


# Standalone coverage run: 2.64s exceeds the fast band.
@pytest.mark.medium
@pytest.mark.parametrize(
    "stale", [None, "README.md", "src/esolangs/registry/well_known.json"]
)
def test_documentation_check_preserves_source_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *,
    stale: str | None,
) -> None:
    from checks import check_docs

    for relative in check_docs.GENERATED:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO_ROOT / relative).read_bytes())
    readme = tmp_path / "README.md"
    if stale == "README.md":
        text = readme.read_text()
        start, end = _markers("PACKAGE-COUNT")
        readme.write_text(
            text.replace(_marked(text, start, end), start + "\nstale\n" + end)
        )
    elif stale is not None:
        (tmp_path / stale).write_text("[]\n")
    before = {
        relative: (
            (tmp_path / relative).read_bytes(),
            (tmp_path / relative).stat().st_mtime_ns,
        )
        for relative in check_docs.GENERATED
    }
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    assert check_docs.stale_generated() == int(stale is not None)
    assert {
        relative: (
            (tmp_path / relative).read_bytes(),
            (tmp_path / relative).stat().st_mtime_ns,
        )
        for relative in check_docs.GENERATED
    } == before
    error = capsys.readouterr().err
    if stale is None:
        assert error == ""
    else:
        assert f"run python scripts/docs/generate.py docs: {stale}" in error


@pytest.mark.parametrize(
    ("missing", "recovery"),
    [
        ("docs/languages.md", "Restore the page before running just docs"),
        ("src/esolangs/registry/well_known.json", "Restore it from Git"),
        ("src/esolangs/languages/EXAMPLES.md", "scripts/docs/generate.py examples"),
    ],
)
def test_missing_generated_docs_report_recovery(
    tmp_path, monkeypatch, capsys, missing, recovery
):
    from checks import check_docs
    from docs import evidence, examples, generate

    for relative in check_docs.GENERATED:
        if relative != missing:
            target = tmp_path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((REPO_ROOT / relative).read_bytes())
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    monkeypatch.setattr(evidence, "update_source_anchors", lambda **_kwargs: False)
    monkeypatch.setattr(examples, "LANGUAGES_DIR", tmp_path / "src/esolangs/languages")
    if missing.endswith("EXAMPLES.md"):
        monkeypatch.setattr(generate, "docs_main", lambda **_kwargs: 0)
    assert check_docs.stale_generated() == 1
    diagnostic = capsys.readouterr().err
    assert missing in diagnostic
    assert recovery in diagnostic
    if missing == "docs/languages.md":
        with pytest.raises(ValueError, match=recovery):
            generate.docs_main(output_root=tmp_path)
    assert not list(tmp_path.glob(".docs-render-*"))


def test_missing_canonical_interpreter_does_not_link_to_an_old_path(tmp_path) -> None:
    module = load_script()
    module.ROOT = tmp_path
    language = next(iter(module.LANGUAGES.values()))
    old = tmp_path / "src/esolangs/runtime" / f"{language.runtime.interpreter}.py"
    old.parent.mkdir(parents=True)
    old.write_text("owned")
    with pytest.raises(FileNotFoundError, match="no canonical interpreter"):
        module._source_link(language.name)
