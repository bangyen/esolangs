"""Fail on stale generated documentation or a dead internal Markdown link.

Generated sections are regenerated into a temporary copy and compared with
the committed files.  Links: a tracked Markdown file must not link to a
missing file or heading.

The documentation cross-references itself heavily -- ``CONTRIBUTING.md``
points at the roadmap's process, the proofs point at the canonical-set rules,
every language entry points at its proof page -- and a section rename leaves
the anchors behind silently.  GitHub renders such a link as ordinary text and
nothing in the suite reads it, so a stale one survives until a reader clicks
it.  Two did: after ``dfabb7ed4`` deleted the roadmap's Parked section, both
``CONTRIBUTING.md`` and ``limitations.md`` still linked ``#parked``.

Only internal links are checked: a relative path must name a tracked file,
and a ``#fragment`` must match a heading (GitHub's slug) or an explicit
``<a id="...">`` anchor in the target.  External URLs are left to CI's own
reachability, which this is not.

Fenced code blocks and inline code spans are stripped first, so an example
that spells a link is not read as one.  Headings are slugged the way GitHub
does -- lowercased, punctuation dropped, spaces to hyphens -- with a
``-1``/``-2`` suffix for a repeated heading, and the Unicode letters some
language names carry are kept.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from docs.anchors import FENCE, anchors

ROOT = Path(__file__).resolve().parents[1]
GENERATED = (
    "README.md",
    "docs/languages.md",
    "docs/proofs/index.md",
    "docs/roadmap.md",
    "docs/usage.md",
    "docs/limitations.md",
    "docs/CONTRIBUTING.md",
    ".github/ISSUE_TEMPLATE/language_request.yml",
    "src/esolangs/languages/generators.py",
)


def _manifest_is_stale() -> bool:
    """Return whether the committed examples manifest differs from its render.

    Only the manifest: regenerating every example program would make this
    check as slow as ``tests/tooling/test_examples.py``, which covers them.
    """
    from docs import examples

    manifest = examples.LANGUAGES_DIR / "EXAMPLES.md"
    return manifest.read_text(encoding="utf-8") != examples.boolean_manifest_text()


_INLINE_CODE = re.compile(r"`[^`\n]*`")
_LINK = re.compile(r"\]\(\s*([^)\s]+)")
_EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|/)", re.IGNORECASE)


def _targets(text: str) -> list[str]:
    """Return the link targets in ``text``, code spans removed."""
    stripped = _INLINE_CODE.sub("", FENCE.sub("", text))
    return [m.group(1) for m in _LINK.finditer(stripped)]


def broken_links(root: Path, files: list[str]) -> list[tuple[str, str]]:
    """Return ``(file, target)`` for every internal link with no target."""
    index = {path: anchors((root / path).read_text(encoding="utf-8")) for path in files}
    broken: list[tuple[str, str]] = []
    for path in files:
        for target in _targets((root / path).read_text(encoding="utf-8")):
            if _EXTERNAL.match(target):
                continue
            target_path, _, fragment = target.partition("#")
            if target_path:
                resolved = _relative(root, (root / path).parent / target_path)
                if resolved is None or not (root / resolved).exists():
                    broken.append((path, target))
                    continue
            else:
                resolved = path
            # A fragment on a non-Markdown file (or one with no index entry)
            # has nothing to resolve against; the file check above is all there is.
            if fragment and fragment not in index.get(resolved, {fragment}):
                broken.append((path, target))
    return broken


def _relative(root: Path, path: Path) -> str | None:
    """Return ``path`` relative to ``root`` as a POSIX string, or None if outside."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def tracked_markdown() -> list[str]:
    """Return the tracked ``*.md`` paths, or every one on disk without git."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", "*.md"],
            cwd=ROOT,
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        skip = {".git", "notes", ".worktrees", ".venv"}
        return sorted(
            p.relative_to(ROOT).as_posix()
            for p in ROOT.rglob("*.md")
            if not skip & set(p.parts)
        )
    return sorted(name for name in result.stdout.split("\0") if name)


def broken_internal_links() -> int:
    """Report every dead internal link; exit nonzero if any."""
    files = tracked_markdown()
    broken = broken_links(ROOT, files)
    if broken:
        print("broken internal documentation links:")
        for path, target in broken:
            print(f"  {path} -> {target}")
        return 1
    return 0


def stale_generated() -> int:
    """Return nonzero when the committed generated sections were stale."""
    # Imported here: they load esolangs, which the links-only pre-commit
    # hook's bare python3 may lack.
    from docs import generate

    before = {path: (ROOT / path).read_bytes() for path in GENERATED}
    with tempfile.TemporaryDirectory(prefix="generated-docs-") as directory:
        output_root = Path(directory)
        for path, content in before.items():
            target = output_root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        result = generate.docs_main(output_root=output_root)
        changed = [
            path
            for path, content in before.items()
            if (output_root / path).read_bytes() != content
        ]
    if changed:
        print(
            "generated documentation is stale; run python "
            "scripts/docs/generate.py docs: " + ", ".join(changed),
            file=sys.stderr,
        )
        return 1
    if _manifest_is_stale():
        print(
            "languages/EXAMPLES.md is stale; run python "
            "scripts/docs/generate.py examples",
            file=sys.stderr,
        )
        return 1
    return result


def main(argv: list[str]) -> int:
    """Run both checks; ``--links`` runs only the link check (pre-commit)."""
    if argv == ["--links"]:
        return broken_internal_links()
    return broken_internal_links() | stale_generated()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
