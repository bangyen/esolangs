"""Compare-before-write, shared by the docs generators."""

from __future__ import annotations

import shutil
from collections.abc import Iterable, Iterator
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


class PublicationRecoveryError(OSError):
    """A failed restore that requires retaining the original files for recovery."""


def replace_batch(pending: list[tuple[Path, Path, Path | None]]) -> set[Path]:
    """Replace the prepared files, restoring their backups on failure."""
    try:
        for staged, path, _ in pending:
            staged.replace(path)
    except BaseException as error:
        failures = []
        for staged, path, backup in reversed(pending):
            if staged.exists():
                continue  # This replacement did not consume its staged file.
            try:
                if backup is None:
                    path.unlink()
                else:
                    backup.replace(path)
            except OSError as restore_error:
                failures.append(f"could not restore {path}: {restore_error}")
                if backup is not None:
                    failures.append(f"original kept at {backup}")
        if failures:
            details = "\n".join(failures)
            raise PublicationRecoveryError(f"{error}\n{details}") from error
        raise
    return {path for _, path, _ in pending}


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


def publish_generated(
    staging: Path, root: Path, *, paths: Iterable[str | Path] = GENERATED_DOCS
) -> set[Path]:
    """Return published destinations after replacing a batch with rollback."""
    saved = root / ".docs-publish"
    saved.mkdir()
    retain = False
    try:
        pending: list[tuple[Path, Path, Path | None]] = []
        for relative in dict.fromkeys(map(Path, paths)):
            staged = staging / relative
            path = root / relative
            if not staged.is_file() or (
                path.is_file() and staged.read_bytes() == path.read_bytes()
            ):
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            backup = None
            if path.exists() or path.is_symlink():
                backup = saved / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, backup, follow_symlinks=False)
            pending.append((staged, path, backup))
        return replace_batch(pending)
    except PublicationRecoveryError:
        retain = True
        raise
    finally:
        if not retain:
            shutil.rmtree(saved)


def write_if_changed(path: Path, text: str, *, encoding: str | None = None) -> bool:
    """Write ``text`` to ``path`` only when its current text differs.

    Return whether the file changed, so a caller can report a write only
    when one happened instead of announcing a phantom update.
    """
    if path.is_file() and path.read_text(encoding=encoding) == text:
        return False
    path.write_text(text, encoding=encoding)
    return True
