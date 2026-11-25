"""Bind saved branch coverage to its checkout and test selection."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .process import write_text
from .receipts import digest, inputs, parse_pytest_execution


def sidecar(data: Path) -> Path:
    """Return the receipt next to its coverage database."""
    return data.with_name(f"{data.name}.inputs.json")


def fingerprint(value: object) -> str:
    """Hash a JSON value independently of key order."""
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def checkout(root: Path, *outputs: Path) -> str:
    """Hash the checkout, excluding coverage outputs stored inside it."""
    paths = (path for data in outputs for path in (data, sidecar(data)))
    exclude = frozenset(
        absolute.relative_to(root).as_posix()
        for path in paths
        if (absolute := path.resolve()).is_relative_to(root)
    )
    return fingerprint(inputs(root, exclude=exclude))


def record(data: Path, state: str, selection: dict[str, Any]) -> None:
    """Write a receipt only after the coverage database is complete."""
    value = {
        "schema": 1,
        "checkout": state,
        "sha256": digest(data),
        "selection": selection,
    }
    write_text(sidecar(data), json.dumps(value, sort_keys=True) + "\n")


def publish(staged: Path, data: Path, state: str, selection: dict[str, Any]) -> None:
    """Publish a coverage pair and restore the previous database on failure."""
    lock = data.with_name(f".coverage.publish-{data.name}")
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise FileExistsError(f"coverage publication already owns {lock}") from error
    backup = lock / "previous"
    receipt = sidecar(staged)
    retain = False
    try:
        had_data = data.exists() or data.is_symlink()
        record(staged, state, selection)
        if had_data:
            shutil.copy2(data, backup, follow_symlinks=False)
        try:
            staged.replace(data)
            receipt.replace(sidecar(data))
        except BaseException as error:
            # A completed replace consumes its staged path.
            if not staged.exists() and receipt.exists():
                try:
                    if had_data:
                        backup.replace(data)
                    else:
                        data.unlink()
                except OSError as restore_error:
                    retain = had_data
                    recovery = f"; previous database kept at {backup}" if retain else ""
                    raise OSError(
                        f"{error}; could not restore {data}: {restore_error}{recovery}"
                    ) from error
            raise
    finally:
        if not retain:
            shutil.rmtree(lock)


def read(data: Path, state: str, *, snapshot: Path | None = None) -> dict[str, Any]:
    """Validate the receipt against the database or a private copy of it."""
    try:
        value = json.loads(sidecar(data).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(
            f"no coverage receipt for {data}; choose a fresh --data file to collect"
        ) from None
    except (OSError, ValueError) as error:
        raise ValueError(f"unreadable coverage receipt for {data}") from error
    if not (
        isinstance(value, dict)
        and value.get("schema") == 1
        and isinstance(selection := value.get("selection"), dict)
    ):
        raise ValueError(f"invalid coverage receipt for {data}")
    if value.get("checkout") != state:
        raise ValueError(f"stale coverage in {data}; the checkout inputs changed")
    if value.get("sha256") != digest(data if snapshot is None else snapshot):
        raise ValueError(f"coverage database {data} does not match its receipt")
    return selection


def completed(path: Path) -> list[str]:
    """Return the selected nodes when pytest completed a real run."""
    try:
        return parse_pytest_execution(path.read_bytes(), 0).selected
    except (OSError, ValueError) as error:
        raise ValueError(
            f"{path}: pytest coverage collection did not complete: {error}"
        ) from error
