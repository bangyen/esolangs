"""Collect independent evidence without allowing corrupt records to pass."""

import json
from collections import Counter
from pathlib import Path
from typing import Any

from _atomic import write_text
from _screen_evidence import read, validate
from _screen_payload import finding


def collect(payload: dict[str, Any]) -> dict[str, Any]:
    """Retain valid evidence and report every rejected record or artifact."""
    records: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    progress = Path(payload["progress"])
    parsed = []
    if progress.exists():
        with progress.open("rb") as stream:
            raw = stream.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            rejected.append(
                {"path": str(progress), "error": "progress exceeds eight MiB"}
            )
        else:
            for line in raw.splitlines():
                try:
                    parsed.append(json.loads(line))
                except ValueError:
                    parsed.append(None)
    records, duplicate_rejections = recover(parsed, payload["expected"])
    rejected.extend(duplicate_rejections)
    for path in sorted(Path(payload["findings"]).glob("*.json")):
        try:
            item = read(path)
            finding(item)
            if item["minimization_status"] == "started":
                item["minimization_status"] = (
                    "timeout" if payload["status"] == "timeout" else "failed"
                )
                write_text(path, json.dumps(item, sort_keys=True))
            findings.append({"path": str(path), **item})
        except (OSError, ValueError, TypeError, KeyError) as error:
            rejected.append({"path": str(path), "error": str(error)})
    return {"cases": records, "findings": findings, "rejected": rejected}


def recover(
    records: list[Any], expected: list[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Revalidate each record, dropping every ambiguous duplicate identity."""
    counts = Counter(
        record.get("case_id")
        for record in records
        if isinstance(record, dict) and isinstance(record.get("case_id"), str)
    )
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        try:
            validate([record], expected, offset=index)
            if counts[record["case_id"]] != 1:
                raise ValueError("duplicate case")
            accepted.append({**record, "ordinal": len(accepted)})
        except (ValueError, TypeError, KeyError) as error:
            rejected.append({"ordinal": index, "error": str(error)})
    return accepted, rejected
