"""Compare-before-write, shared by the docs generators."""

from __future__ import annotations

from pathlib import Path


def write_if_changed(path: Path, text: str, *, encoding: str | None = None) -> bool:
    """Write ``text`` to ``path`` only when its current text differs.

    Return whether the file changed, so a caller can report a write only
    when one happened instead of announcing a phantom update.
    """
    if path.is_file() and path.read_text(encoding=encoding) == text:
        return False
    path.write_text(text, encoding=encoding)
    return True
