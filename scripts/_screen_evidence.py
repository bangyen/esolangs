"""Validate case identities and load reusable bounded-screen evidence."""

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _screen_payload import validate as validate_payload

LIMIT = 32 * 1024 * 1024
REUSABLE = {"measured", "stepped", "executed", "compared", "refused"}
_CACHE: dict[str, dict[str, Any]] | None = None


def case_id(*parts: object) -> str:
    """Hash a case's scope and exact corpus input."""
    return hashlib.sha256(json.dumps(parts, separators=(",", ":")).encode()).hexdigest()


def read(path: Path) -> dict[str, Any]:
    """Read one bounded JSON object, refusing oversized or malformed evidence."""
    with path.open("rb") as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError("screen evidence exceeds 32 MiB")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("screen evidence must be an object")
    return value


def checksum(record: dict[str, Any]) -> str:
    """Hash immutable evidence fields independently of replay bookkeeping."""
    payload = {
        key: value
        for key, value in record.items()
        if key not in {"ordinal", "reused", "evidence_sha256"}
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def validate(records: list[Any], expected: list[str], *, offset: int = 0) -> None:
    """Reject duplicate, unplanned or malformed case records."""
    seen = set()
    allowed = set(expected)
    if len(allowed) != len(expected):
        raise ValueError("duplicate planned case")
    for index, record in enumerate(records):
        if (
            not isinstance(record, dict)
            or type(record.get("ordinal")) is not int
            or record["ordinal"] != index + offset
            or type(record.get("rows")) is not int
            or record["rows"] < 0
            or not isinstance(record.get("status"), str)
            or record["status"] not in REUSABLE | {"dropped", "skipped"}
            or not isinstance(record.get("case_id"), str)
            or record["case_id"] not in allowed
            or record["case_id"] in seen
            or type(record.get("case_count", 1)) is not int
            or record.get("case_count", 1) != 1
            or record.get("evidence_sha256") != checksum(record)
        ):
            raise ValueError("duplicate, unplanned or invalid screen case")
        validate_payload(record)
        seen.add(record["case_id"])


def resume(
    path: Path, identity: dict[str, Any], plan: dict[str, Any], screen: str
) -> list[dict[str, Any]]:
    """Reuse only matching source, settings and corpus; interrupted cases retry."""
    value = read(path)
    if (
        value.get("schema") != 3
        or value.get("checkout") != identity["checkout"]
        or value.get("settings") != identity["settings"]
        or value.get("runtime") != identity["runtime"]
        or value.get("plan") != plan
        or value.get("screen") != screen
        or value.get("status") in {"source-changed", "invalid-evidence"}
        or not isinstance(value.get("cases"), list)
    ):
        raise ValueError("resume source, settings or corpus do not match")
    validate(value["cases"], plan["case_ids"])
    return [record for record in value["cases"] if record["status"] in REUSABLE]


def reused(identifier: str) -> dict[str, Any] | None:
    """Return a validated reusable record available to this worker."""
    global _CACHE
    if _CACHE is None:
        name = os.environ.get("ESOLANGS_SCREEN_RESUME")
        records = read(Path(name))["cases"] if name else []
        _CACHE = {record["case_id"]: record for record in records}
    return _CACHE.get(identifier)
