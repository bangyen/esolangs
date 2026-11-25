"""The docs gate flags dead anchors and passes real cross-references."""

import subprocess
from functools import partial
from pathlib import Path

import pytest

from tests.tooling.script_support import load

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "checks" / "check_docs.py"


load_script = partial(load, SCRIPT)


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


def test_link_destinations_allow_angles_parentheses_and_titles(tmp_path: Path) -> None:
    checker = load_script()
    files = _tree(
        tmp_path,
        {
            "a.md": (
                '[with spaces](<b b.md#yes> "Optional title")\n'
                "[balanced](b(c(d)).md#yes 'Another title')\n"
                r"[escaped](b\(c\(d\)\).md#yes)"
                "\n"
                "[missing](<b b.md#no>) [missing](b(c(d)).md#no)\n"
            ),
            "b b.md": "# Yes\n",
            "b(c(d)).md": "# Yes\n",
        },
    )
    assert checker.broken_links(tmp_path, files) == [
        ("a.md", "b b.md#no"),
        ("a.md", "b(c(d)).md#no"),
    ]


def test_only_used_reference_destinations_are_checked(tmp_path: Path) -> None:
    checker = load_script()
    files = _tree(
        tmp_path,
        {
            "a.md": (
                "[nested [text]][  lIVE   link ] [external][]\n"
                "[missing][] [shortcut] `[unused]` "
                "```text`[unused]``` \\[unused]\n\n"
                "[Live Link]:\n <b b.md#yes> 'Title'\n"
                "[live link]: ignored-duplicate.md\n"
                "[external]: https://example.com/x#y\n"
                "[missing]: gone(extra).md\n"
                "[shortcut]: <b b.md#no>\n"
                "[unused]: also-gone.md\n\n"
                "~~~\n[unused]\n~~~\n"
            ),
            "b b.md": "# Yes\n",
        },
    )
    assert checker.broken_links(tmp_path, files) == [
        ("a.md", "gone(extra).md"),
        ("a.md", "b b.md#no"),
    ]


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


def test_comments_hide_links_definitions_headings_and_explicit_anchors(tmp_path):
    checker = load_script()
    files = _tree(
        tmp_path,
        {
            "a.md": (
                "<!-- [draft](missing.md)\n[ref]: bad.md\n-->\n"
                "[from a definition][ref]\n\n[ref]: b.md#visible\n\n"
                "[hidden heading](b.md#hidden) [hidden tag](b.md#ghost)\n"
            ),
            "b.md": (
                "# Visi<!-- unpublished text -->ble\n\n"
                '<!--\n# Hidden\n<a id="ghost"></a>\n-->\n'
            ),
        },
    )
    assert checker.broken_links(tmp_path, files) == [
        ("a.md", "b.md#hidden"),
        ("a.md", "b.md#ghost"),
    ]


def test_literal_comment_openers_leave_following_links_visible(tmp_path):
    checker = load_script()
    files = _tree(
        tmp_path,
        {
            "a.md": (
                "```\n<!--\n```\n`<!--` and \\<!-- are literal.\n\n[visible](gone.md)\n"
            ),
        },
    )
    assert checker.broken_links(tmp_path, files) == [("a.md", "gone.md")]


def test_a_repeated_heading_gets_a_suffix_anchor(tmp_path: Path) -> None:
    checker = load_script()
    files = _tree(
        tmp_path,
        {"a.md": "## Notes\n\n## Notes\n", "b.md": "[second](a.md#notes-1)\n"},
    )
    assert checker.broken_links(tmp_path, files) == []


def test_underlined_headings_share_the_atx_anchor_order(tmp_path: Path) -> None:
    checker = load_script()
    files = _tree(
        tmp_path,
        {
            "guide.md": (
                "Setup\n=====\n\n## Setup-1\n\nSetup\n-----\n\n"
                "Long\nheading\n=====\n\nParagraph\n\n---\n\n"
                "```md\nHidden\n---\n```\n\n"
                "    Indented code\n---\n\n- List item\nContinuation\n---\n"
            ),
            "README.md": "\n\n".join(
                f"[{slug}](guide.md#{slug})"
                for slug in (
                    "setup",
                    "setup-1",
                    "setup-2",
                    "longheading",
                    "paragraph",
                    "hidden",
                    "indented-code",
                    "continuation",
                )
            ),
        },
    )
    assert checker.broken_links(tmp_path, files) == [
        ("README.md", f"guide.md#{slug}")
        for slug in ("paragraph", "hidden", "indented-code", "continuation")
    ]


@pytest.mark.parametrize(
    ("headings", "valid", "invalid"),
    [
        (("Setup", "Setup-1", "Setup"), "setup-2", "setup-1-1"),
        (("Setup", "Setup", "Setup-1"), "setup-1-1", "setup-2"),
    ],
)
def test_heading_suffixes_skip_slugs_already_used(tmp_path, headings, valid, invalid):
    checker = load_script()
    files = _tree(
        tmp_path,
        {
            "a.md": "".join(f"## {heading}\n\n" for heading in headings),
            "b.md": f"[valid](a.md#{valid})\n\n[invalid](a.md#{invalid})\n",
        },
    )
    assert checker.broken_links(tmp_path, files) == [("b.md", f"a.md#{invalid}")]


def test_a_tilde_fenced_heading_is_not_an_anchor(tmp_path: Path) -> None:
    checker = load_script()
    files = _tree(
        tmp_path,
        {"a.md": "~~~\n## Hidden\n~~~\n", "b.md": "[x](a.md#hidden)\n"},
    )
    assert checker.broken_links(tmp_path, files) == [("b.md", "a.md#hidden")]


@pytest.mark.parametrize(
    ("opening", "closing"),
    [
        ("````md\n```\n", "`````\n"),
        ("   ~~~md\n~~~ with trailing text\n```\n", " ~~~ \t\n"),
        ("  ```md\n", ""),
    ],
)
def test_fence_boundaries_hide_examples(
    tmp_path: Path, opening: str, closing: str
) -> None:
    checker = load_script()
    files = _tree(
        tmp_path,
        {
            "a.md": f"# Before\n\n{opening}# Hidden\n[example](gone.md)\n{closing}"
            + ("# After\n\n[real link](gone.md)\n" if closing else ""),
            "b.md": "[before](a.md#before) [hidden](a.md#hidden)"
            + (" [after](a.md#after)" if closing else ""),
        },
    )
    expected = [("a.md", "gone.md")] if closing else []
    assert checker.broken_links(tmp_path, files) == [*expected, ("b.md", "a.md#hidden")]


def test_proof_evidence_shares_the_link_gates_anchors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only rendered headings and explicit anchors count as evidence."""
    load_script()  # puts scripts/ on the path, as the gate itself does
    from docs import proof_status

    page = tmp_path / "page.md"
    page.write_text(
        '<a name="kept"></a>\n~~~\n## Hidden\n~~~\n<!--\n## Draft\n-->\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(proof_status, "ROOT", tmp_path)
    proof_status._check_evidence("page.md#kept", precise=True)
    with pytest.raises(ValueError, match="missing evidence anchor"):
        proof_status._check_evidence("page.md#hidden", precise=True)
    with pytest.raises(ValueError, match="missing evidence anchor"):
        proof_status._check_evidence("page.md#draft", precise=True)


def test_the_committed_tree_has_no_dead_links() -> None:
    checker = load_script()
    assert "README.md" in checker._tracked_paths(checker.ROOT)
    assert checker.broken_links(checker.ROOT) == []


def test_links_use_index_paths_and_decode_destinations(tmp_path: Path) -> None:
    checker = load_script()
    _tree(
        tmp_path,
        {
            "guide.md": (
                "[local only](local.py) [tracked code](code/example.py)\n"
                "[directory](code/) [encoded](my%20page%23.md#caf%C3%A9)\n"
            ),
            "local.py": "",
            "code/example.py": "",
            "my page#.md": "# Café\n",
        },
    )
    for args in (("init", "-q"), ("add", "guide.md", "code", "my page#.md")):
        subprocess.run(
            ["git", *args], cwd=tmp_path, capture_output=True, check=True, timeout=10
        )
    assert checker.broken_links(tmp_path) == [("guide.md", "local.py")]
    (tmp_path / "code/example.py").unlink()
    assert checker.broken_links(tmp_path) == [
        ("guide.md", "local.py"),
        ("guide.md", "code/example.py"),
    ]
