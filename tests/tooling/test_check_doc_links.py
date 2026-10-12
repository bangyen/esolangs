"""The doc-link gate flags dead anchors and passes real cross-references."""

from pathlib import Path
from typing import Any

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


def test_the_committed_tree_has_no_dead_links() -> None:
    checker = load_script()
    files = checker.tracked_markdown()
    assert files, "no Markdown files found"
    assert checker.broken_links(checker.ROOT, files) == []
