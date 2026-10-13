"""The doc-link gate flags dead anchors and passes real cross-references."""

from pathlib import Path
from typing import Any

import pytest

from tests.tooling.script_support import load

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "checks" / "check_doc_links.py"


def load_script() -> Any:
    return load(SCRIPT)


def _tree(tmp_path: Path, files: dict[str, str]) -> list[str]:
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return sorted(files)


def test_a_dead_heading_anchor_is_reported(tmp_path: Path) -> None:
    checker = load_script()
    files = _tree(
        tmp_path,
        {"a.md": "See [the rules](b.md#canonical-set).\n", "b.md": "## A set\n"},
    )
    assert checker.broken_links(tmp_path, files) == [("a.md", "b.md#canonical-set")]


def test_a_live_heading_and_explicit_anchor_pass(tmp_path: Path) -> None:
    checker = load_script()
    files = _tree(
        tmp_path,
        {
            "a.md": (
                "See [rules](b.md#canonical-set) and [bound](b.md#factor-bound).\n"
            ),
            "b.md": '## Canonical set\n\n- Factor: <a id="factor-bound"></a> floor\n',
        },
    )
    assert checker.broken_links(tmp_path, files) == []


def test_a_missing_relative_file_is_reported(tmp_path: Path) -> None:
    checker = load_script()
    files = _tree(tmp_path, {"a.md": "See [there](gone.md).\n"})
    assert checker.broken_links(tmp_path, files) == [("a.md", "gone.md")]


def test_external_links_and_code_spans_are_ignored(tmp_path: Path) -> None:
    checker = load_script()
    files = _tree(
        tmp_path,
        {
            "a.md": (
                "[site](https://example.com/x#y) and `[code](gone.md#z)`\n\n"
                "```\n[fenced](also-gone.md)\n```\n"
            )
        },
    )
    assert checker.broken_links(tmp_path, files) == []


def test_a_repeated_heading_gets_a_suffix_anchor(tmp_path: Path) -> None:
    checker = load_script()
    files = _tree(
        tmp_path,
        {"a.md": "## Notes\n\n## Notes\n", "b.md": "[second](a.md#notes-1)\n"},
    )
    assert checker.broken_links(tmp_path, files) == []


def test_a_tilde_fenced_heading_is_not_an_anchor(tmp_path: Path) -> None:
    checker = load_script()
    files = _tree(
        tmp_path,
        {"a.md": "~~~\n## Hidden\n~~~\n", "b.md": "[x](a.md#hidden)\n"},
    )
    assert checker.broken_links(tmp_path, files) == [("b.md", "a.md#hidden")]


def test_proof_evidence_shares_the_link_gates_anchors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``name=`` anchor is evidence; a heading in a ``~~~`` fence is not."""
    load_script()  # puts scripts/ on the path, as the gate itself does
    from docs import proof_status

    page = tmp_path / "page.md"
    page.write_text('<a name="kept"></a>\n~~~\n## Hidden\n~~~\n', encoding="utf-8")
    monkeypatch.setattr(proof_status, "ROOT", tmp_path)
    proof_status._check_evidence("page.md#kept", precise=True)  # noqa: SLF001
    with pytest.raises(ValueError, match="missing evidence anchor"):
        proof_status._check_evidence("page.md#hidden", precise=True)  # noqa: SLF001


def test_the_committed_tree_has_no_dead_links() -> None:
    checker = load_script()
    files = checker.tracked_markdown()
    assert files, "no Markdown files found"
    assert checker.broken_links(checker.ROOT, files) == []
