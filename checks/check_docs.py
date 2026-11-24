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

import os
import posixpath
import re
import string
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

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
    "src/esolangs/registry/scaling.json",
)


def _manifest_is_stale() -> bool:
    """Return whether the committed examples manifest differs from its render.

    Only the manifest: regenerating every example program would make this
    check as slow as ``tests/tooling/test_examples.py``, which covers them.
    """
    from docs import examples

    manifest = examples.LANGUAGES_DIR / "EXAMPLES.md"
    return manifest.read_text(encoding="utf-8") != examples.boolean_manifest_text()


_INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`)[^\n]*?(?<!`)\1(?!`)")
_ESCAPED = rf"\\([{re.escape(string.punctuation)}])"
_UNESCAPE = re.compile(_ESCAPED)
_BRACKET = re.compile(rf"{_ESCAPED}|[\[\]]")
_LABEL = r"\[((?:\\.|[^\[\]\\\n])*)\]"
_REFERENCE = re.compile(_LABEL)
_DEFINITION = re.compile(rf"^ {{0,3}}{_LABEL}:[ \t]*(?:\n[ \t]*)?", re.MULTILINE)
_TITLE = r"""(?:"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|\((?:\\.|[^()\\\n])*\))"""
_INLINE_END = re.compile(rf"(?:\s+{_TITLE})?\s*\)")
_DEFINITION_END = re.compile(rf"(?:[ \t]+{_TITLE})?[ \t]*$", re.MULTILINE)
_EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|/)", re.IGNORECASE)


def _destination(text: str, start: int) -> tuple[str, int] | None:
    """Read a bracketed or bare destination through its last character."""
    angle = text.startswith("<", start)
    start += int(angle)
    end = start
    depth = 0
    while end < len(text):
        char = text[end]
        escaped = _UNESCAPE.match(text, end)
        if escaped is not None:
            end = escaped.end()
            continue
        if angle:
            if char == ">":
                return _UNESCAPE.sub(r"\1", text[start:end]), end + 1
            if char in "<\n":
                return None
        else:
            if char.isspace() or (char == ")" and depth == 0):
                break
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
        end += 1
    if angle or depth:
        return None
    return _UNESCAPE.sub(r"\1", text[start:end]), end


def _label(text: str) -> str:
    return " ".join(text.split()).casefold()


def _references(text: str, visible: str) -> tuple[dict[str, str], str]:
    references: dict[str, str] = {}
    parts: list[str] = []
    cursor = 0
    for match in _DEFINITION.finditer(visible):
        if match.start() < cursor:
            continue
        label = _label(text[match.start(1) : match.end(1)])
        dest = _destination(text, match.end())
        if not label or dest is None:
            continue
        target, end = dest
        tail = _DEFINITION_END.match(text, end)
        if tail is None or end == match.end():
            continue
        references.setdefault(label, target)
        parts.extend(
            (visible[cursor : match.start()], " " * (tail.end() - match.start()))
        )
        cursor = tail.end()
    parts.append(visible[cursor:])
    return references, "".join(parts)


def _targets(text: str) -> Iterator[str]:
    """Yield destinations from inline links and resolved references."""
    text = FENCE.sub("\n", text)
    visible = _INLINE_CODE.sub(lambda match: " " * len(match[0]), text)
    references, visible = _references(text, visible)
    openings: list[int] = []
    cursor = 0
    for bracket in _BRACKET.finditer(visible):
        start, end = bracket.span()
        if start < cursor:
            continue
        if bracket[0] == "[":
            openings.append(end)
        elif bracket[0] == "]" and openings:
            opening = openings.pop()
            if visible.startswith("(", end):
                dest_start = end + 1
                while dest_start < len(text) and text[dest_start].isspace():
                    dest_start += 1
                dest = _destination(text, dest_start)
                if dest is not None and (tail := _INLINE_END.match(text, dest[1])):
                    yield dest[0]
                    cursor = tail.end()
                    continue
            explicit = _REFERENCE.match(visible, end)
            label = _label(text[opening:start])
            if explicit is not None and explicit[1]:
                label = _label(text[explicit.start(1) : explicit.end(1)])
            if label in references:
                yield references[label]
                if explicit is not None:
                    cursor = explicit.end()


def broken_links(root: Path, files: list[str] | None = None) -> list[tuple[str, str]]:
    """List internal links missing from the checkout or index."""
    tracked = _tracked_paths(root)
    if files is None:
        if tracked is None:
            skip = {".git", "notes", ".worktrees", ".venv"}
            files = sorted(
                path.relative_to(root).as_posix()
                for path in root.rglob("*.md")
                if not skip & set(path.relative_to(root).parts)
            )
        else:
            files = sorted(path for path in tracked if path.endswith(".md"))
    # Git trees have directories only where they contain a tracked path.
    targets = (
        None
        if tracked is None
        else tracked
        | {
            parent.as_posix()
            for path in tracked
            for parent in PurePosixPath(path).parents
        }
    )
    pages = {
        path: (root / path).read_text(encoding="utf-8")
        for path in files
        if (root / path).is_file()
    }
    root = root.resolve()
    index = {path: anchors(text) for path, text in pages.items()}
    broken: list[tuple[str, str]] = []
    for path, text in pages.items():
        for target in _targets(text):
            if _EXTERNAL.match(target):
                continue
            target_path, _, fragment = target.partition("#")
            target_path = unquote(
                target_path.partition("?")[0], errors="surrogateescape"
            )
            if target_path:
                resolved = posixpath.normpath(
                    posixpath.join(posixpath.dirname(path), target_path)
                )
                candidate = root / resolved
                if (
                    (targets is not None and resolved not in targets)
                    or not candidate.exists()
                    or not candidate.resolve().is_relative_to(root)
                ):
                    broken.append((path, target))
                    continue
            else:
                resolved = path
            # A fragment on a non-Markdown file (or one with no index entry)
            # has nothing to resolve against; the file check above is all there is.
            fragment = unquote(fragment)
            if fragment and fragment not in index.get(resolved, {fragment}):
                broken.append((path, target))
    return broken


def _tracked_paths(root: Path) -> set[str] | None:
    """Read the Git index, allowing the disk-only check in source archives."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "-z"],
            cwd=root,
            capture_output=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        if (root / ".git").exists():
            raise ValueError(
                "could not read the Git index for documentation links"
            ) from error
        return None
    return {os.fsdecode(name) for name in result.stdout.split(b"\0") if name}


def broken_internal_links() -> int:
    """Report every dead internal link; exit nonzero if any."""
    try:
        broken = broken_links(ROOT)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
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
    from docs.evidence import update_source_anchors

    from docs import generate

    if update_source_anchors(check=True):
        print(
            "generator size anchors are stale; run "
            "python scripts/docs/generate.py anchors",
            file=sys.stderr,
        )
        return 1

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
