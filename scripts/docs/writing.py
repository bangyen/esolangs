"""Compare-before-write, shared by the docs generators."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

GENERATED_DOCS = (
    "docs/proofs/index.md",
    "src/esolangs/registry/scaling.json",
    "src/esolangs/registry/well_known.json",
    "README.md",
    "docs/languages.md",
    "docs/usage.md",
    "docs/limitations.md",
)


def generated_sources(
    root: Path, *, require_generated: bool = False
) -> Iterator[tuple[str, Path]]:
    """Yield existing inputs and require the Markdown pages with source prose."""
    for name in GENERATED_DOCS:
        path = root / name
        if path.is_file():
            yield name, path
        elif path.exists():
            raise ValueError(f"{name}: expected a file")
        elif name.endswith(".md"):
            raise ValueError(
                f"{name}: missing Markdown source. "
                "Restore the page before running just docs."
            )
        elif require_generated:
            raise ValueError(
                f"{name}: missing generated file. "
                "Restore it from Git, then run just docs."
            )


def write_if_changed(path: Path, text: str, *, encoding: str | None = None) -> bool:
    """Write ``text`` to ``path`` only when its current text differs.

    Return whether the file changed, so a caller can report a write only
    when one happened instead of announcing a phantom update.
    """
    if path.is_file() and path.read_text(encoding=encoding) == text:
        return False
    path.write_text(text, encoding=encoding)
    return True
