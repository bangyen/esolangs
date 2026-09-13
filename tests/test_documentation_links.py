"""Local Markdown links must name files that ship with the repository."""

from __future__ import annotations

import pathlib
import re
from urllib.parse import unquote

ROOT = pathlib.Path(__file__).parents[1]
_LINK = re.compile(r"(?<!!)\[[^]]*\]\(([^ )]+)(?:\s+[^)]*)?\)")
_DOCUMENTS = (
    ROOT / "README.md",
    *sorted((ROOT / "docs").rglob("*.md")),
    *sorted((ROOT / "src" / "esolangs" / "examples").glob("*.md")),
)


def test_every_local_markdown_link_resolves() -> None:
    """Check shipped documentation, including package example guides."""
    missing: list[str] = []
    for document in _DOCUMENTS:
        for target in _LINK.findall(document.read_text(encoding="utf-8")):
            path, _, _fragment = unquote(target).partition("#")
            if not path or "://" in path or path.startswith("mailto:"):
                continue
            if not (document.parent / path).exists():
                missing.append(f"{document.relative_to(ROOT)} -> {target}")
    assert not missing, "broken local Markdown links:\n" + "\n".join(missing)
