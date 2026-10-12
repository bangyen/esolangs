"""Fail when a tracked Markdown file links to a missing file or heading.

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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_LINK = re.compile(r"\]\(\s*([^)\s]+)")
_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$", re.MULTILINE)
_EXPLICIT_ANCHOR = re.compile(r"<a\s+(?:id|name)=\"([^\"]+)\"")
_EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|/)", re.IGNORECASE)


def slug(heading: str) -> str:
    """Return GitHub's anchor slug for a heading.

    Lowercase; drop everything but letters, digits, underscores, hyphens and
    spaces; turn spaces into hyphens.  ``&`` and the like vanish rather than
    becoming ``amp``, which is what ``github-slugger`` does.
    """
    text = heading.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


def anchors(text: str) -> set[str]:
    """Return every heading and explicit anchor a reader can link to in ``text``."""
    found = {slug(m.group(1)) for m in _HEADING.finditer(_FENCE.sub("", text))}
    found |= {m.group(1) for m in _EXPLICIT_ANCHOR.finditer(text)}
    # GitHub disambiguates a repeated heading, but a repeated anchor is a
    # document bug rather than a link target, so only headings get suffixes.
    seen: dict[str, int] = {}
    for match in _HEADING.finditer(_FENCE.sub("", text)):
        base = slug(match.group(1))
        count = seen.get(base, 0)
        seen[base] = count + 1
        if count:
            found.add(f"{base}-{count}")
    return found


def _targets(text: str) -> list[str]:
    """Return the link targets in ``text``, code spans removed."""
    stripped = _INLINE_CODE.sub("", _FENCE.sub("", text))
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


def main() -> int:
    """Report every dead internal link; exit nonzero if any."""
    files = tracked_markdown()
    broken = broken_links(ROOT, files)
    if broken:
        print("broken internal documentation links:")
        for path, target in broken:
            print(f"  {path} -> {target}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
