"""Bind saved branch coverage to its checkout and test selection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .process import write_text
from .receipts import digest, inputs


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
    """Hash staged bytes so a concurrent writer cannot change their receipt."""
    record(staged, state, selection)
    staged.replace(data)
    sidecar(staged).replace(sidecar(data))


def read(data: Path, state: str) -> dict[str, Any]:
    """Reject missing, mismatched, and stale coverage receipts."""
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
    if value.get("sha256") != digest(data):
        raise ValueError(f"coverage database {data} does not match its receipt")
    return selection


def completed(path: Path) -> list[str]:
    """Return the selected nodes when pytest completed a real run."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        selected = value["selected"]
        if (
            isinstance(selected, list)
            and selected
            and value["schema"] == 1
            and value["exitstatus"] == 0
            and not value["selection"]["collect_only"]
            and value["passed_calls"]
            and not value["failed_calls"]
            and selected == value["finished"]
        ):
            return selected
    except (OSError, KeyError, TypeError, ValueError):
        pass
    raise ValueError("pytest coverage collection did not complete")
